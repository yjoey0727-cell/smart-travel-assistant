from __future__ import annotations

import asyncio
import re
import uuid
from datetime import date
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal, get_db
from ..domain.itinerary import item_from_candidate
from ..domain.models import Candidate
from ..domain.seed import seed_candidates
from ..models import ExportJob, PlanRun, Trip
from ..schemas import (
    AddItemRequest,
    ExportOut,
    ExportRequest,
    PlanRequest,
    PlanRunOut,
    ReorderRequest,
    RunInfo,
    SessionInfo,
    TripSummary,
    UpdateItemRequest,
)
from ..services.amap import AmapClient
from ..services.exporter import _chrome_path, process_export
from ..services.run_manager import event_stream, get_runtime, start_run
from ..services.trip_service import finalize_trip, trip_summary

router = APIRouter(prefix="/api/v1")


def _session(request: Request, response: Response) -> str:
    sid = request.cookies.get(settings.session_cookie)
    if not sid:
        sid = request.headers.get("x-session-id") or uuid.uuid4().hex
    response.set_cookie(
        settings.session_cookie,
        sid,
        max_age=settings.session_days * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return sid


async def _get_trip(trip_id: str, sid: str) -> Trip:
    async with SessionLocal() as db:
        trip = await db.get(Trip, trip_id)
        if not trip or trip.session_id != sid:
            raise HTTPException(status_code=404, detail="行程不存在")
        return trip


def _origin_center(trip: Trip) -> Optional[Tuple[float, float]]:
    center = (trip.data.get("meta") or {}).get("originCenter")
    if not center:
        return None
    try:
        return float(center["lng"]), float(center["lat"])
    except Exception:
        return None


async def _recalculate(trip: Trip) -> dict:
    data = await finalize_trip(trip.data, AmapClient(), _origin_center(trip))
    trip.version = int(trip.version or 1) + 1
    data["version"] = trip.version
    trip.data = data
    trip.title = data["title"]
    async with SessionLocal() as db:
        merged = await db.merge(trip)
        await db.commit()
        await db.refresh(merged)
    return data


@router.get("/health")
async def health():
    return {"ok": True, "app": settings.app_name}


@router.get("/session", response_model=SessionInfo)
async def session_info(request: Request, response: Response):
    sid = _session(request, response)
    return SessionInfo(
        session_id=sid,
        demo_mode=not settings.amap_configured,
        amap_configured=settings.amap_configured,
        llm_configured=settings.llm_configured,
        demo_city=settings.demo_city,
        export_ready=bool(_chrome_path()),
    )


@router.post("/plan-runs", response_model=PlanRunOut, status_code=202)
async def create_plan_run(payload: PlanRequest, request: Request, response: Response):
    sid = _session(request, response)
    run_id = await start_run(payload, sid)
    return PlanRunOut(run_id=run_id)


@router.get("/plan-runs/{run_id}/events")
async def plan_run_events(run_id: str, request: Request, response: Response):
    sid = _session(request, response)
    header_last = request.headers.get("last-event-id") or "0"
    try:
        last_id = int(header_last)
    except ValueError:
        last_id = 0
    return StreamingResponse(
        event_stream(run_id, sid, last_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/plan-runs/{run_id}", response_model=RunInfo)
async def plan_run_info(run_id: str, request: Request, response: Response):
    sid = _session(request, response)
    runtime = get_runtime(run_id)
    if runtime:
        if runtime.session_id != sid:
            raise HTTPException(status_code=403, detail="无权访问该规划任务")
        return RunInfo(
            run_id=run_id,
            status=runtime.status,
            stage=runtime.stage,
            progress=runtime.progress,
            trip_id=runtime.trip_id,
            error=runtime.error,
        )
    async with SessionLocal() as db:
        run = await db.get(PlanRun, run_id)
        if not run or run.session_id != sid:
            raise HTTPException(status_code=404, detail="规划任务不存在")
        return RunInfo(
            run_id=run.id,
            status=run.status,
            stage=run.stage,
            progress=run.progress,
            trip_id=run.trip_id,
            error=run.error,
        )


@router.get("/trips", response_model=List[TripSummary])
async def list_trips(request: Request, response: Response):
    sid = _session(request, response)
    async with SessionLocal() as db:
        result = await db.execute(
            select(Trip).where(Trip.session_id == sid).order_by(Trip.updated_at.desc()).limit(30)
        )
        trips = result.scalars().all()
    return [trip_summary(t.data, t.updated_at.isoformat() if t.updated_at else None) for t in trips]


@router.get("/trips/{trip_id}")
async def get_trip(trip_id: str, request: Request, response: Response):
    sid = _session(request, response)
    trip = await _get_trip(trip_id, sid)
    return trip.data


@router.delete("/trips/{trip_id}")
async def delete_trip(trip_id: str, request: Request, response: Response):
    sid = _session(request, response)
    async with SessionLocal() as db:
        trip = await db.get(Trip, trip_id)
        if not trip or trip.session_id != sid:
            raise HTTPException(status_code=404, detail="行程不存在")
        await db.delete(trip)
        await db.commit()
    return {"ok": True}


def _find_item(data: dict, item_id: str):
    for day in data.get("days") or []:
        for index, item in enumerate(day.get("items") or []):
            if item.get("id") == item_id:
                return day, index, item
    return None, None, None


@router.post("/trips/{trip_id}/items")
async def add_item(trip_id: str, payload: AddItemRequest, request: Request, response: Response):
    sid = _session(request, response)
    trip = await _get_trip(trip_id, sid)
    day = next(
        (d for d in trip.data.get("days") or [] if int(d.get("dayIndex") or 0) == payload.day_index),
        None,
    )
    if not day:
        raise HTTPException(status_code=404, detail="当天不存在")
    poi = payload.poi
    candidate = Candidate(
        candidate_id="manual",
        poi_id=poi.poi_id,
        name=poi.name,
        kind=poi.type,
        address=poi.address,
        lng=poi.lng,
        lat=poi.lat,
        rating=poi.rating,
        cost_cents=poi.cost_cents,
        cost_basis=poi.cost_basis,
        duration_min=poi.duration_min,
        tags=poi.tags,
        area=poi.area or "",
        description=poi.description or "",
        image=poi.image,
        source=poi.source,
        confidence=poi.confidence,
        booking_url=poi.booking_url,
    )
    item = item_from_candidate(
        candidate,
        (trip.data.get("meta") or {}).get("travelers") or {},
        start_time="12:00",
        duration_min=poi.duration_min,
        note="手动添加 · 参考价",
    )
    items = day.setdefault("items", [])
    insert_at = len(items)
    if payload.after_item_id:
        for idx, existing in enumerate(items):
            if existing.get("id") == payload.after_item_id:
                insert_at = idx + 1
                break
    else:
        # 默认把新内容放在合理位置：酒店最后，景点在晚餐/酒店之前，餐饮在酒店之前。
        if poi.type == "hotel":
            insert_at = len(items)
        else:
            for idx, existing in enumerate(items):
                existing_type = existing.get("type")
                existing_start = existing.get("startTime") or "00:00"
                if existing_type == "hotel":
                    insert_at = idx
                    break
                if poi.type == "attraction" and existing_type == "meal" and existing_start >= "16:00":
                    insert_at = idx
                    break
    items.insert(insert_at, item)
    data = await _recalculate(trip)
    return data


@router.patch("/trips/{trip_id}/items/{item_id}")
async def update_item(
    trip_id: str,
    item_id: str,
    payload: UpdateItemRequest,
    request: Request,
    response: Response,
):
    sid = _session(request, response)
    trip = await _get_trip(trip_id, sid)
    day, index, item = _find_item(trip.data, item_id)
    if not day or item is None:
        raise HTTPException(status_code=404, detail="行程条目不存在")
    if payload.day_index is not None and payload.day_index != int(day.get("dayIndex") or 0):
        target = next(
            (d for d in trip.data.get("days") or [] if int(d.get("dayIndex") or 0) == payload.day_index),
            None,
        )
        if not target:
            raise HTTPException(status_code=404, detail="目标日期不存在")
        day["items"].pop(index)
        target.setdefault("items", []).append(item)
        day = target
    if payload.start_time is not None:
        item["startTime"] = payload.start_time
    if payload.duration_min is not None:
        item["durationMin"] = payload.duration_min
    if payload.notes is not None:
        item["notes"] = payload.notes
    if payload.locked is not None:
        item["locked"] = payload.locked
    data = await _recalculate(trip)
    return data


@router.delete("/trips/{trip_id}/items/{item_id}")
async def delete_item(trip_id: str, item_id: str, request: Request, response: Response):
    sid = _session(request, response)
    trip = await _get_trip(trip_id, sid)
    day, index, item = _find_item(trip.data, item_id)
    if not day or item is None:
        raise HTTPException(status_code=404, detail="行程条目不存在")
    day["items"].pop(index)
    data = await _recalculate(trip)
    return data


@router.put("/trips/{trip_id}/days/{day_index}/order")
async def reorder_day(
    trip_id: str,
    day_index: int,
    payload: ReorderRequest,
    request: Request,
    response: Response,
):
    sid = _session(request, response)
    trip = await _get_trip(trip_id, sid)
    day = next(
        (d for d in trip.data.get("days") or [] if int(d.get("dayIndex") or 0) == day_index),
        None,
    )
    if not day:
        raise HTTPException(status_code=404, detail="当天不存在")
    items = day.get("items") or []
    by_id = {item.get("id"): item for item in items}
    ordered = [by_id[item_id] for item_id in payload.item_ids if item_id in by_id]
    ordered += [item for item in items if item.get("id") not in payload.item_ids]
    # 酒店固定放在当天最后，避免被误拖到上午后导致时间轴整体错乱。
    ordered = [item for item in ordered if item.get("type") != "hotel"] + [
        item for item in ordered if item.get("type") == "hotel"
    ]
    day["items"] = ordered
    data = await _recalculate(trip)
    return data


@router.post("/trips/{trip_id}/budget/recalculate")
async def recalculate_budget(trip_id: str, request: Request, response: Response):
    sid = _session(request, response)
    trip = await _get_trip(trip_id, sid)
    return await _recalculate(trip)


@router.get("/poi/search")
async def search_poi(
    request: Request,
    response: Response,
    city: str = Query(..., min_length=1),
    keyword: str = Query("", max_length=60),
    type: str = Query("attraction", pattern="^(attraction|meal|hotel)$"),
):
    _session(request, response)
    amap = AmapClient()
    results: List[Candidate] = []
    if amap.configured:
        queries = [keyword] if keyword else {
            "attraction": ["景点", "公园", "博物馆"],
            "meal": ["川菜", "火锅", "小吃"],
            "hotel": ["酒店"],
        }[type]
        for query in queries:
            results.extend(await amap.search(city, query, type, limit=10))
    if not results:
        seed_items = seed_candidates(city)
        q = keyword.strip().lower()
        results = [
            c
            for c in seed_items
            if c.kind == type
            and (
                not q
                or q in c.name.lower()
                or q in c.description.lower()
                or any(q in tag.lower() for tag in c.tags)
            )
        ]
    dedup = {}
    for item in results:
        dedup.setdefault(item.poi_id, item)
    return {"items": [item.to_public() for item in list(dedup.values())[:16]]}


@router.post("/trips/{trip_id}/exports", response_model=ExportOut)
async def create_export(
    trip_id: str,
    payload: ExportRequest,
    request: Request,
    response: Response,
):
    sid = _session(request, response)
    trip = await _get_trip(trip_id, sid)
    job_id = "exp_" + uuid.uuid4().hex[:12]
    async with SessionLocal() as db:
        job = ExportJob(
            id=job_id,
            trip_id=trip_id,
            session_id=sid,
            format=payload.format,
            status="queued",
        )
        db.add(job)
        await db.commit()
    asyncio.create_task(process_export(job_id, trip.data, payload.format))
    return ExportOut(export_id=job_id, status="queued", format=payload.format)


@router.get("/exports/{export_id}", response_model=ExportOut)
async def get_export(export_id: str, request: Request, response: Response):
    sid = _session(request, response)
    async with SessionLocal() as db:
        job = await db.get(ExportJob, export_id)
        if not job or job.session_id != sid:
            raise HTTPException(status_code=404, detail="导出任务不存在")
        download = None
        if job.status == "succeeded":
            download = f"/api/v1/exports/{job.id}/download"
        return ExportOut(
            export_id=job.id,
            status=job.status,
            format=job.format,
            download_url=download,
            error=job.error,
        )


@router.get("/exports/{export_id}/download")
async def download_export(export_id: str, request: Request, response: Response):
    sid = _session(request, response)
    async with SessionLocal() as db:
        job = await db.get(ExportJob, export_id)
        if not job or job.session_id != sid:
            raise HTTPException(status_code=404, detail="导出任务不存在")
        if job.status != "succeeded" or not job.file_path:
            raise HTTPException(status_code=409, detail="文件尚未生成")
        path = Path(job.file_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail="文件已过期或不存在")
        suffix = path.suffix.lower()
        media = job.media_type or ("application/pdf" if suffix == ".pdf" else "image/png")
        trip = await db.get(Trip, job.trip_id)
        raw_title = ((trip.title if trip else "旅行") + "行程单")
        title = re.sub(r'[\\/:*?"<>|]', "_", raw_title)
        filename = f"{title}{suffix}"
        return FileResponse(path, media_type=media, filename=filename)
