from __future__ import annotations

import asyncio
import math
import uuid
from datetime import date, timedelta
from typing import List, Optional, Tuple

from ..domain.budget import compute_budget
from ..domain.itinerary import build_day_routes, item_from_candidate, reflow_all
from ..domain.seed import CITY_PROFILES, city_center
from ..schemas import PlanRequest

DAY_COLORS = ["#2563eb", "#f97316", "#0f766e", "#7c3aed", "#db2777", "#0891b2", "#ca8a04"]


def new_trip_id() -> str:
    return "trp_" + uuid.uuid4().hex[:14]


def new_day_id() -> str:
    return "day_" + uuid.uuid4().hex[:10]


def make_title(city: str, day_count: int, draft: dict, prefs: dict) -> str:
    theme = ""
    for day in draft.get("days") or []:
        if day.get("theme"):
            theme = str(day["theme"])
            break
    if not theme:
        bits = (prefs.get("scenery") or [])[:1] + (prefs.get("food") or [])[:1]
        theme = " · ".join(bits) or "城市漫游"
    return f"{city} {day_count} 日 · {theme}"


def materialize_trip(
    request: PlanRequest,
    draft: dict,
    center: Tuple[float, float],
    origin_center: Optional[Tuple[float, float]],
    adcode: Optional[str],
    meta_extra: dict,
) -> dict:
    request_data = request.model_dump(by_alias=True)
    travelers = request_data.get("travelers") or {}
    day_count = request.day_count
    start = request.start_date
    days = []
    for idx in range(day_count):
        draft_day = next(
            (d for d in draft.get("days") or [] if int(d.get("dayIndex", 0)) == idx + 1),
            None,
        )
        date_value = (start + timedelta(days=idx)).isoformat()
        if not draft_day:
            days.append(
                {
                    "dayIndex": idx + 1,
                    "date": date_value,
                    "theme": "自由活动",
                    "summary": "这一天还没有安排，可以添加景点或餐厅。",
                    "items": [],
                }
            )
            continue
        items = []
        for spec in draft_day.get("items") or []:
            candidate = spec["candidate"]
            items.append(
                item_from_candidate(
                    candidate,
                    travelers,
                    start_time=spec.get("startTime") or "09:00",
                    duration_min=spec.get("durationMin"),
                    note=spec.get("note") or "",
                )
            )
        days.append(
            {
                "dayIndex": idx + 1,
                "date": date_value,
                "theme": draft_day.get("theme") or "城市漫游",
                "summary": draft_day.get("summary") or "",
                "items": items,
            }
        )

    prefs = request_data.get("preferences") or {}
    city = request.destination.city
    meta = {
        "planner": draft.get("planner") or "rule",
        "rationale": draft.get("rationale") or "",
        "origin": request.origin,
        "originCenter": (
            {"lng": origin_center[0], "lat": origin_center[1]} if origin_center else None
        ),
        "transport": request_data.get("transport") or {},
        "travelers": travelers,
        "preferences": prefs,
        "budgetLimitCents": int((request_data.get("budget") or {}).get("totalCents") or 0),
        "hotelLevel": prefs.get("hotelLevel") or "comfort",
        "notes": request.notes,
        "generatedAt": date.today().isoformat(),
        "demo": bool(meta_extra.get("demo")),
        "amap": bool(meta_extra.get("amap")),
        "llm": bool(meta_extra.get("llm")),
        "dayCount": day_count,
    }
    return {
        "id": new_trip_id(),
        "version": 1,
        "title": make_title(city, day_count, draft, prefs),
        "destination": {
            "city": city,
            "adcode": adcode or (CITY_PROFILES.get(city) or {}).get("adcode"),
            "center": {"lng": center[0], "lat": center[1]},
        },
        "startDate": request.start_date.isoformat(),
        "endDate": request.end_date.isoformat(),
        "days": days,
        "routes": [],
        "budget": {},
        "meta": meta,
        "createdAt": date.today().isoformat(),
        "updatedAt": date.today().isoformat(),
    }


def normalize_days(data: dict) -> None:
    for day in data.get("days") or []:
        items = day.get("items") or []
        if not items:
            continue
        hotels = [item for item in items if item.get("type") == "hotel"]
        others = [item for item in items if item.get("type") != "hotel"]
        if hotels and items[-1].get("type") != "hotel":
            day["items"] = others + hotels


async def finalize_trip(data: dict, amap, origin_center: Optional[Tuple[float, float]]) -> dict:
    normalize_days(data)
    city = (data.get("destination") or {}).get("city") or ""
    meta = data.get("meta") or {}
    local_pref = ((meta.get("transport") or {}).get("local")) or "mixed"
    travelers = meta.get("travelers") or {}
    sem = asyncio.Semaphore(3)

    async def one_day(day: dict) -> List[dict]:
        async with sem:
            return await build_day_routes(day, amap, city, local_pref, travelers)

    route_groups = await asyncio.gather(*(one_day(day) for day in data.get("days") or []))
    routes: List[dict] = []
    for group in route_groups:
        routes.extend(group)
    data["routes"] = routes
    reflow_all(data.get("days") or [], routes)
    data["budget"] = compute_budget(data, origin_center)
    data["updatedAt"] = date.today().isoformat()
    return data


async def resolve_origin_center(amap, origin: Optional[str]) -> Optional[Tuple[float, float]]:
    if not origin:
        return None
    if origin in ("成都", "成都市区"):
        return city_center("成都")
    from ..domain.seed import CITY_CENTERS

    if origin in CITY_CENTERS:
        return CITY_CENTERS[origin]
    if amap.configured:
        return await amap.geocode(origin)
    return None


def budget_nights(day_count: int) -> int:
    return max(0, day_count - 1)


def trip_summary(data: dict, updated_at: Optional[str] = None) -> dict:
    budget = data.get("budget") or {}
    cover = None
    for day in data.get("days") or []:
        for item in day.get("items") or []:
            if item.get("image"):
                cover = item["image"]
                break
        if cover:
            break
    return {
        "id": data.get("id"),
        "title": data.get("title"),
        "city": (data.get("destination") or {}).get("city"),
        "startDate": data.get("startDate"),
        "endDate": data.get("endDate"),
        "days": len(data.get("days") or []),
        "totalCents": int(budget.get("totalCents") or 0),
        "cover": cover,
        "updatedAt": updated_at or data.get("updatedAt"),
        "version": int(data.get("version") or 1),
    }


def day_color(day_index: int) -> str:
    return DAY_COLORS[(day_index - 1) % len(DAY_COLORS)]
