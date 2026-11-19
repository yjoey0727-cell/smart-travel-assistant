from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional, Set

from ..db import SessionLocal
from ..models import PlanRun, Trip
from ..schemas import PlanRequest
from .agent import PlanningAgent, PlanningError

logger = logging.getLogger(__name__)


@dataclass
class RunRuntime:
    run_id: str
    session_id: str
    status: str = "queued"
    stage: str = "queued"
    progress: int = 0
    trip_id: Optional[str] = None
    error: Optional[str] = None
    events: List[dict] = field(default_factory=list)
    subscribers: Set[asyncio.Queue] = field(default_factory=set)
    done: bool = False


_RUNS: Dict[str, RunRuntime] = {}


def get_runtime(run_id: str) -> Optional[RunRuntime]:
    return _RUNS.get(run_id)


def _publish(runtime: RunRuntime, event: dict) -> None:
    event = dict(event)
    event["id"] = len(runtime.events) + 1
    runtime.events.append(event)
    if event.get("type") == "stage":
        runtime.stage = event.get("stage") or runtime.stage
        runtime.progress = int(event.get("progress") or runtime.progress)
    if event.get("type") == "plan":
        runtime.trip_id = event.get("tripId")
    if event.get("type") == "error":
        runtime.error = event.get("message")
    for queue in list(runtime.subscribers):
        try:
            queue.put_nowait(event)
        except Exception:
            pass


async def _finish_subscribers(runtime: RunRuntime) -> None:
    for queue in list(runtime.subscribers):
        try:
            queue.put_nowait(None)
        except Exception:
            pass


async def start_run(request: PlanRequest, session_id: str) -> str:
    run_id = "run_" + uuid.uuid4().hex[:14]
    request_json = request.model_dump(mode="json", by_alias=True)
    async with SessionLocal() as db:
        run = PlanRun(
            id=run_id,
            session_id=session_id,
            status="queued",
            stage="queued",
            progress=0,
            request=request_json,
            events=[],
        )
        db.add(run)
        await db.commit()
    runtime = RunRuntime(run_id=run_id, session_id=session_id)
    _RUNS[run_id] = runtime
    asyncio.create_task(_execute(run_id, request, runtime))
    return run_id


async def _execute(run_id: str, request: PlanRequest, runtime: RunRuntime) -> None:
    runtime.status = "running"
    runtime.stage = "normalize"
    async with SessionLocal() as db:
        run = await db.get(PlanRun, run_id)
        if run:
            run.status = "running"
            run.stage = "normalize"
            await db.commit()

    async def emit(event: dict) -> None:
        _publish(runtime, event)

    try:
        agent = PlanningAgent()
        trip_data = await agent.run(request, emit)
        async with SessionLocal() as db:
            trip = Trip(
                id=trip_data["id"],
                session_id=runtime.session_id,
                city=trip_data["destination"]["city"],
                title=trip_data["title"],
                start_date=trip_data["startDate"],
                end_date=trip_data["endDate"],
                version=int(trip_data.get("version") or 1),
                data=trip_data,
            )
            db.add(trip)
            run = await db.get(PlanRun, run_id)
            runtime.status = "succeeded"
            runtime.stage = "done"
            runtime.progress = 100
            runtime.trip_id = trip_data["id"]
            if run:
                run.status = "succeeded"
                run.stage = "done"
                run.progress = 100
                run.trip_id = trip_data["id"]
            await db.commit()
        _publish(
            runtime,
            {
                "type": "plan",
                "tripId": trip_data["id"],
                "version": trip_data.get("version", 1),
                "title": trip_data.get("title"),
                "demo": (trip_data.get("meta") or {}).get("demo", True),
                "planner": (trip_data.get("meta") or {}).get("planner", "rule"),
            },
        )
        runtime.done = True
        _publish(
            runtime,
            {
                "type": "done",
                "demo": (trip_data.get("meta") or {}).get("demo", True),
                "planner": (trip_data.get("meta") or {}).get("planner", "rule"),
            },
        )
        try:
            async with SessionLocal() as db:
                run = await db.get(PlanRun, run_id)
                if run:
                    run.events = runtime.events
                    await db.commit()
        except Exception:
            logger.exception("failed to persist plan events")
    except PlanningError as exc:
        await _fail(run_id, runtime, str(exc))
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("planning failed")
        await _fail(run_id, runtime, f"规划失败：{exc}")
    finally:
        await _finish_subscribers(runtime)


async def _fail(run_id: str, runtime: RunRuntime, message: str) -> None:
    runtime.status = "failed"
    runtime.stage = "failed"
    runtime.error = message
    _publish(runtime, {"type": "error", "message": message})
    runtime.done = True
    try:
        async with SessionLocal() as db:
            run = await db.get(PlanRun, run_id)
            if run:
                run.status = "failed"
                run.stage = "failed"
                run.error = message
                run.events = runtime.events
                await db.commit()
    except Exception:
        logger.exception("failed to persist plan run failure")


def _sse(event: dict) -> str:
    return (
        f"event: {event.get('type', 'message')}\n"
        f"id: {event.get('id', 0)}\n"
        f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
    )


async def event_stream(run_id: str, session_id: str, last_event_id: int = 0) -> AsyncGenerator[str, None]:
    runtime = _RUNS.get(run_id)
    if runtime is None:
        async with SessionLocal() as db:
            run = await db.get(PlanRun, run_id)
            if not run or run.session_id != session_id:
                yield _sse({"type": "error", "message": "规划任务不存在或已过期", "id": 0})
                return
            events = run.events or []
            for event in events:
                if int(event.get("id", 0)) > last_event_id:
                    yield _sse(event)
            if run.status == "succeeded" and not (events and events[-1].get("type") == "done"):
                yield _sse({"type": "done", "id": len(events) + 1})
            elif run.status == "failed":
                yield _sse(
                    {
                        "type": "error",
                        "message": run.error or "规划失败",
                        "id": len(run.events or []) + 1,
                    }
                )
            return

    if runtime.session_id != session_id:
        yield _sse({"type": "error", "message": "无权访问该规划任务", "id": 0})
        return

    queue: asyncio.Queue = asyncio.Queue()
    runtime.subscribers.add(queue)
    try:
        for event in runtime.events:
            if int(event.get("id", 0)) > last_event_id:
                yield _sse(event)
        if runtime.done:
            return
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=15)
            except asyncio.TimeoutError:
                yield ": ping\n\n"
                continue
            if item is None:
                break
            yield _sse(item)
    finally:
        runtime.subscribers.discard(queue)
