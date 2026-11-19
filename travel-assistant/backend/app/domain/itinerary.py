from __future__ import annotations

import math
import uuid
from typing import Dict, List, Optional, Tuple

from .models import Candidate

BUFFER_MIN = 10


def new_item_id() -> str:
    return "itm_" + uuid.uuid4().hex[:12]


def parse_hhmm(value: str, default: int = 540) -> int:
    try:
        hour, minute = [int(x) for x in (value or "").split(":")]
        return max(0, min(23 * 60 + 59, hour * 60 + minute))
    except Exception:
        return default


def format_hhmm(minutes: int) -> str:
    minutes = max(0, min(23 * 60 + 59, int(minutes)))
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def haversine_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    lng1, lat1 = a
    lng2, lat2 = b
    radius = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lng = math.radians(lng2 - lng1)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius * math.asin(min(1.0, math.sqrt(h)))


def cost_for_candidate(candidate: Candidate, travelers: dict) -> int:
    adults = int(travelers.get("adults") or 1)
    children = int(travelers.get("children") or 0)
    units = adults + children * 0.5
    if candidate.kind == "hotel":
        return int(candidate.cost_cents)
    if candidate.kind == "attraction":
        return int(round(candidate.cost_cents * units))
    return int(round(candidate.cost_cents * (adults + children)))


def item_from_candidate(
    candidate: Candidate,
    travelers: dict,
    start_time: str = "09:00",
    duration_min: Optional[int] = None,
    note: str = "",
) -> dict:
    duration = int(duration_min or candidate.duration_min)
    start = parse_hhmm(start_time)
    amount = cost_for_candidate(candidate, travelers)
    return {
        "id": new_item_id(),
        "type": candidate.kind,
        "title": candidate.name,
        "poiId": candidate.poi_id,
        "location": {"lng": candidate.lng, "lat": candidate.lat},
        "address": candidate.address,
        "startTime": format_hhmm(start),
        "endTime": format_hhmm(start + duration),
        "durationMin": duration,
        "cost": {
            "amountCents": amount,
            "currency": "CNY",
            "category": {"attraction": "ticket", "meal": "meal", "hotel": "hotel"}[candidate.kind],
            "basis": {"attraction": "group", "meal": "group", "hotel": "room_night"}[candidate.kind],
            "source": candidate.source,
            "confidence": candidate.confidence,
            "note": "参考价，以商家为准",
        },
        "notes": note,
        "locked": False,
        "rating": candidate.rating,
        "tags": candidate.tags,
        "image": candidate.image,
        "description": candidate.description,
        "bookingUrl": candidate.booking_url,
        "area": candidate.area,
    }


def choose_mode(distance_km: float, local_pref: str) -> str:
    if distance_km < 1.5:
        return "walking"
    if local_pref == "taxi":
        return "driving"
    if distance_km <= 8:
        return "transit"
    return "driving"


def _fallback_route(
    origin: Tuple[float, float], dest: Tuple[float, float], mode: str, headcount: int
) -> dict:
    distance = haversine_km(origin, dest)
    speed = {"walking": 4.5, "transit": 18.0, "driving": 26.0}.get(mode, 20.0)
    duration = max(3, int(round(distance / speed * 60 + (4 if mode != "walking" else 0))))
    if mode == "walking":
        cost = 0
    elif mode == "transit":
        cost = 400 * max(1, headcount)
    else:
        cost = int(1000 + 250 * distance)
    return {
        "distanceM": int(distance * 1000),
        "durationMin": duration,
        "polyline": [[origin[0], origin[1]], [dest[0], dest[1]]],
        "status": "estimated",
        "provider": "fallback",
        "mode": mode,
        "costCents": cost,
    }


async def build_day_routes(day: dict, amap, city: str, local_pref: str, travelers: dict) -> List[dict]:
    items = day.get("items") or []
    legs: List[dict] = []
    headcount = max(1, int(travelers.get("adults") or 1) + int(travelers.get("children") or 0))
    for idx in range(len(items) - 1):
        first = items[idx]
        second = items[idx + 1]
        origin = (float(first["location"]["lng"]), float(first["location"]["lat"]))
        dest = (float(second["location"]["lng"]), float(second["location"]["lat"]))
        distance = haversine_km(origin, dest)
        mode = choose_mode(distance, local_pref)
        route = await amap.route(origin, dest, mode, city) if amap.configured else None
        if route:
            route["mode"] = mode
            if mode == "walking":
                route["costCents"] = 0
            elif mode == "transit":
                route["costCents"] = 400 * headcount
            else:
                route["costCents"] = int(1000 + 250 * distance)
        else:
            route = _fallback_route(origin, dest, mode, headcount)
        route.update(
            {
                "dayIndex": int(day.get("dayIndex") or 1),
                "fromItemId": first["id"],
                "toItemId": second["id"],
            }
        )
        legs.append(route)
    return legs


def _leg_minutes(route: dict) -> int:
    return max(1, int(route.get("durationMin") or 0))


def reflow_day(day: dict, routes: List[dict]) -> None:
    items = day.get("items") or []
    leg_map = {(leg["fromItemId"], leg["toItemId"]): leg for leg in routes}
    current = 9 * 60
    for idx, item in enumerate(items):
        item_type = item.get("type")
        if item_type == "meal":
            earliest = 11 * 60 + 30 if idx <= 2 else 17 * 60 + 30
            # 午餐/晚餐按时间判断，避免把晚餐排到中午
            hour = parse_hhmm(item.get("startTime", ""), 12 * 60) // 60
            earliest = 17 * 60 + 30 if hour >= 16 else 11 * 60 + 30
        elif item_type == "hotel":
            earliest = 20 * 60
        else:
            earliest = 9 * 60
        start = max(current, earliest)
        duration = max(15, int(item.get("durationMin") or 90))
        item["startTime"] = format_hhmm(start)
        item["endTime"] = format_hhmm(start + duration)
        current = start + duration
        if idx < len(items) - 1:
            leg = leg_map.get((item.get("id"), items[idx + 1].get("id")))
            current += (_leg_minutes(leg) if leg else 12) + BUFFER_MIN


def reflow_all(days: List[dict], routes: List[dict]) -> None:
    for day in days:
        day_routes = [r for r in routes if int(r.get("dayIndex") or 0) == int(day.get("dayIndex") or 0)]
        reflow_day(day, day_routes)


def nearest_order(items: List[Candidate], start: Tuple[float, float]) -> List[Candidate]:
    remaining = list(items)
    ordered: List[Candidate] = []
    cursor = start
    while remaining:
        nxt = min(remaining, key=lambda c: haversine_km(cursor, (c.lng, c.lat)))
        ordered.append(nxt)
        cursor = (nxt.lng, nxt.lat)
        remaining.remove(nxt)
    return ordered


def split_days(attractions: List[Candidate], day_count: int) -> List[List[Candidate]]:
    if not attractions:
        return [[] for _ in range(day_count)]
    buckets: List[List[Candidate]] = [[] for _ in range(day_count)]
    for idx, item in enumerate(attractions):
        buckets[idx % day_count].append(item)
    return buckets


def clone_candidate_with_id(candidate: Candidate, candidate_id: str) -> Candidate:
    data = candidate.model_dump()
    data["candidate_id"] = candidate_id
    return Candidate(**data)
