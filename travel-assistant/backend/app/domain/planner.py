from __future__ import annotations

import math
from collections import Counter
from typing import Dict, List, Optional, Tuple

from .itinerary import haversine_km, nearest_order
from .models import Candidate


def _score_attraction(candidate: Candidate, prefs: dict) -> float:
    score = candidate.rating * 12.0 + candidate.priority
    tags = set(candidate.tags)
    if "必去" in tags:
        score += 45
    for tag in prefs.get("scenery") or []:
        if tag in tags or tag in candidate.name:
            score += 22
    for tag in prefs.get("food") or []:
        if tag in tags:
            score += 8
    if candidate.cost_cents == 0:
        score += 3
    for avoid in prefs.get("avoid") or []:
        if avoid in tags or avoid in candidate.name:
            score -= 80
    return score


def _hotel_score(candidate: Candidate, level: str) -> float:
    price = candidate.cost_cents / 100
    target = {"budget": 300, "comfort": 650, "premium": 1400}.get(level, 650)
    return candidate.rating * 15 - abs(price - target) / 20


def choose_hotel(hotels: List[Candidate], level: str) -> Optional[Candidate]:
    if not hotels:
        return None
    return max(hotels, key=lambda c: _hotel_score(c, level))


def _food_near(foods: List[Candidate], point: Tuple[float, float], used: set) -> Optional[Candidate]:
    candidates = [f for f in foods if f.poi_id not in used] or foods
    if not candidates:
        return None
    return min(candidates, key=lambda f: haversine_km(point, (f.lng, f.lat)))


def _theme_for_day(attractions: List[Candidate], prefs: dict | None = None) -> str:
    tags = Counter()
    preferred = set((prefs or {}).get("scenery") or [])
    meaningful = {"自然", "历史", "人文", "博物馆", "古镇", "街区", "亲子", "夜景", "艺术", "公园", "园林", "寺庙", "温泉", "海岛"}
    for item in attractions:
        for tag in item.tags:
            if tag in meaningful:
                tags[tag] += 1
                if tag in preferred:
                    tags[tag] += 2
    top = [tag for tag, _ in tags.most_common(2)]
    return " · ".join(top) if top else "城市漫游"


def build_rule_plan(
    candidates: List[Candidate], request: dict, center: Tuple[float, float]
) -> dict:
    day_count = int(request["_day_count"])
    prefs = request.get("preferences") or {}
    travelers = request.get("travelers") or {}
    pace = prefs.get("pace") or "balanced"
    per_day = {"relaxed": 2, "balanced": 3, "packed": 4}.get(pace, 3)

    attractions_all = sorted(
        [c for c in candidates if c.kind == "attraction"],
        key=lambda c: _score_attraction(c, prefs),
        reverse=True,
    )
    # 默认优先市区景点，避免把 50km 外的近郊景点硬塞进半日行程；用户可在编辑页手动添加。
    nearby = [c for c in attractions_all if haversine_km(center, (c.lng, c.lat)) <= 25]
    attractions = nearby or attractions_all
    foods = sorted([c for c in candidates if c.kind == "meal"], key=lambda c: c.rating, reverse=True)
    hotels = [c for c in candidates if c.kind == "hotel"]
    hotel = choose_hotel(hotels, prefs.get("hotel_level") or prefs.get("hotelLevel") or "comfort")

    max_attractions = min(len(attractions), per_day * day_count)
    # 将候选景点均衡分配到各天，并优先选择离当天已有点更近的景点。
    # 这样既能保证西湖/灵隐等必去点不会全挤在第一天，也能减少跨区折返。
    pool = attractions[:max_attractions]
    buckets: List[List[Candidate]] = [[] for _ in range(day_count)]
    centroids: List[Tuple[float, float]] = [center for _ in range(day_count)]
    for item in pool:
        allowed = [i for i in range(day_count) if len(buckets[i]) < per_day]
        if not allowed:
            break

        def day_cost(day_idx: int) -> float:
            dist = haversine_km(centroids[day_idx], (item.lng, item.lat))
            same_area = 1 if buckets[day_idx] and (buckets[day_idx][0].area == item.area) else 0
            return dist - (4 if same_area else 0) + 8 * len(buckets[day_idx])

        best = min(allowed, key=day_cost)
        bucket = buckets[best]
        bucket.append(item)
        centroids[best] = (
            sum(c.lng for c in bucket) / len(bucket),
            sum(c.lat for c in bucket) / len(bucket),
        )

    days: List[dict] = []
    used_food: set = set()

    for day_index in range(1, day_count + 1):
        day_attractions = buckets[day_index - 1] if day_index - 1 < len(buckets) else []
        if not day_attractions and attractions:
            # 候选不足时，允许复用评分最高的景点，保证每天有内容
            day_attractions = [attractions[0]]
        if day_attractions:
            day_attractions = sorted(
                day_attractions,
                key=lambda c: (c.priority, c.rating),
                reverse=True,
            )
            first = day_attractions[0]
            rest = day_attractions[1:]
            day_attractions = [first] + nearest_order(rest, (first.lng, first.lat))

        specs: List[dict] = []
        lunch = None
        dinner = None
        if day_attractions:
            lunch_point = (day_attractions[0].lng, day_attractions[0].lat)
            lunch = _food_near(foods, lunch_point, used_food)
            if lunch:
                used_food.add(lunch.poi_id)
            dinner_point = (
                (hotel.lng, hotel.lat) if hotel else (day_attractions[-1].lng, day_attractions[-1].lat)
            )
            dinner = _food_near(foods, dinner_point, used_food)
            if dinner:
                used_food.add(dinner.poi_id)

            specs.append(
                {
                    "candidate": day_attractions[0],
                    "startTime": "09:00",
                    "durationMin": day_attractions[0].duration_min,
                    "note": "建议提前查看预约与闭馆信息",
                }
            )
            if lunch:
                specs.append(
                    {
                        "candidate": lunch,
                        "startTime": "12:00",
                        "durationMin": lunch.duration_min,
                        "note": "午餐 · 参考人均消费",
                    }
                )
            for idx, attraction in enumerate(day_attractions[1:], start=1):
                specs.append(
                    {
                        "candidate": attraction,
                        "startTime": "14:00" if idx == 1 else "16:00",
                        "durationMin": attraction.duration_min,
                        "note": "",
                    }
                )
            if dinner:
                specs.append(
                    {
                        "candidate": dinner,
                        "startTime": "18:00",
                        "durationMin": dinner.duration_min,
                        "note": "晚餐 · 建议错峰或提前排号",
                    }
                )
        else:
            lunch = _food_near(foods, center, used_food)
            if lunch:
                used_food.add(lunch.poi_id)
                specs.append(
                    {
                        "candidate": lunch,
                        "startTime": "12:00",
                        "durationMin": lunch.duration_min,
                        "note": "午餐",
                    }
                )
            dinner = _food_near(foods, center, used_food)
            if dinner:
                used_food.add(dinner.poi_id)
                specs.append(
                    {
                        "candidate": dinner,
                        "startTime": "18:00",
                        "durationMin": dinner.duration_min,
                        "note": "晚餐",
                    }
                )

        if hotel and day_index < day_count:
            specs.append(
                {
                    "candidate": hotel,
                    "startTime": "20:00",
                    "durationMin": 30,
                    "note": f"入住 · 连住 {day_count - 1} 晚，参考价以酒店为准",
                }
            )

        days.append(
            {
                "dayIndex": day_index,
                "theme": _theme_for_day(day_attractions, prefs) if day_attractions else "城市慢游",
                "summary": "按地理邻近安排，减少来回折返。" if day_attractions else "轻松用餐，自由活动。",
                "items": specs,
            }
        )

    return {
        "days": days,
        "rationale": "根据偏好评分、地理邻近和营业时段生成，预算与路线由服务端重新核算。",
        "planner": "rule",
    }


def _candidate_map(candidates: List[Candidate]) -> Dict[str, Candidate]:
    return {c.candidate_id: c for c in candidates}


def _default_hotel(candidates: List[Candidate], level: str) -> Optional[Candidate]:
    return choose_hotel([c for c in candidates if c.kind == "hotel"], level)


def build_llm_plan(
    payload: dict,
    candidates: List[Candidate],
    request: dict,
    center: Tuple[float, float],
    planner_name: str = "llm",
) -> dict:
    day_count = int(request["_day_count"])
    prefs = request.get("preferences") or {}
    by_id = _candidate_map(candidates)
    attractions = sorted(
        [c for c in candidates if c.kind == "attraction"],
        key=lambda c: _score_attraction(c, prefs),
        reverse=True,
    )
    foods = sorted([c for c in candidates if c.kind == "meal"], key=lambda c: c.rating, reverse=True)
    hotel = _default_hotel(candidates, prefs.get("hotel_level") or prefs.get("hotelLevel") or "comfort")

    payload_days = payload.get("days") or []
    by_day: Dict[int, List[dict]] = {}
    for raw_day in payload_days:
        try:
            day_index = int(raw_day.get("dayIndex"))
        except Exception:
            continue
        if not (1 <= day_index <= day_count):
            continue
        specs = []
        for raw_item in raw_day.get("items") or []:
            candidate = by_id.get(str(raw_item.get("candidateId") or ""))
            if not candidate:
                continue
            start = str(raw_item.get("startTime") or "09:00")
            duration = raw_item.get("durationMin") or candidate.duration_min
            specs.append(
                {
                    "candidate": candidate,
                    "startTime": start,
                    "durationMin": int(duration),
                    "note": str(raw_item.get("note") or "")[:160],
                }
            )
        by_day[day_index] = specs[:8]

    used_food: set = set()
    used_attractions: set = set()
    days: List[dict] = []
    for day_index in range(1, day_count + 1):
        raw_specs = by_day.get(day_index, [])
        # 最后一天不安排酒店；同一景点尽量不重复
        seen_here = set()
        specs: List[dict] = []
        for spec in raw_specs:
            candidate = spec["candidate"]
            if candidate.kind == "hotel" and day_index == day_count:
                continue
            if candidate.poi_id in seen_here:
                continue
            if candidate.kind == "attraction" and candidate.poi_id in used_attractions:
                continue
            seen_here.add(candidate.poi_id)
            if candidate.kind == "attraction":
                used_attractions.add(candidate.poi_id)
            if candidate.kind == "meal":
                used_food.add(candidate.poi_id)
            specs.append(spec)

        has_attraction = any(s["candidate"].kind == "attraction" for s in specs)
        if not has_attraction and attractions:
            for attraction in attractions:
                if attraction.poi_id not in used_attractions:
                    used_attractions.add(attraction.poi_id)
                    specs.insert(
                        0,
                        {
                            "candidate": attraction,
                            "startTime": "09:00",
                            "durationMin": attraction.duration_min,
                            "note": "补充安排",
                        },
                    )
                    break
            else:
                specs.insert(
                    0,
                    {
                        "candidate": attractions[0],
                        "startTime": "09:00",
                        "durationMin": attractions[0].duration_min,
                        "note": "补充安排",
                    },
                )

        meal_specs = [s for s in specs if s["candidate"].kind == "meal"]
        if len(meal_specs) < 2:
            attraction_specs = [s for s in specs if s["candidate"].kind == "attraction"]
            lunch_point = (
                (attraction_specs[0]["candidate"].lng, attraction_specs[0]["candidate"].lat)
                if attraction_specs
                else center
            )
            dinner_point = (
                (hotel.lng, hotel.lat)
                if hotel
                else (
                    (attraction_specs[-1]["candidate"].lng, attraction_specs[-1]["candidate"].lat)
                    if attraction_specs
                    else center
                )
            )
            if not any(s["candidate"].kind == "meal" and s["startTime"] < "16:00" for s in specs):
                lunch = _food_near(foods, lunch_point, used_food)
                if lunch:
                    used_food.add(lunch.poi_id)
                    specs.append(
                        {
                            "candidate": lunch,
                            "startTime": "12:00",
                            "durationMin": lunch.duration_min,
                            "note": "午餐 · 系统补充",
                        }
                    )
            if len([s for s in specs if s["candidate"].kind == "meal"]) < 2:
                dinner = _food_near(foods, dinner_point, used_food)
                if dinner:
                    used_food.add(dinner.poi_id)
                    specs.append(
                        {
                            "candidate": dinner,
                            "startTime": "18:00",
                            "durationMin": dinner.duration_min,
                            "note": "晚餐 · 系统补充",
                        }
                    )

        if hotel and day_index < day_count and not any(
            s["candidate"].kind == "hotel" for s in specs
        ):
            specs.append(
                {
                    "candidate": hotel,
                    "startTime": "20:00",
                    "durationMin": 30,
                    "note": f"入住 · 连住 {day_count - 1} 晚",
                }
            )

        specs.sort(key=lambda s: s.get("startTime") or "09:00")
        day_attractions = [s["candidate"] for s in specs if s["candidate"].kind == "attraction"]
        days.append(
            {
                "dayIndex": day_index,
                "theme": str(
                    (next((d for d in payload_days if int(d.get("dayIndex", 0)) == day_index), {}) or {}).get(
                        "theme"
                    )
                    or _theme_for_day(day_attractions, prefs)
                )[:40],
                "summary": str(
                    (next((d for d in payload_days if int(d.get("dayIndex", 0)) == day_index), {}) or {}).get(
                        "summary"
                    )
                    or "由 AI 根据你的偏好生成，可随时调整。"
                )[:120],
                "items": specs,
            }
        )

    return {
        "days": days,
        "rationale": str(payload.get("rationale") or "AI 根据候选 POI、偏好和路程生成。")[:300],
        "planner": planner_name,
    }
