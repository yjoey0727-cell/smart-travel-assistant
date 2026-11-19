from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

BUFFER_RATE = 0.08


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


def _route_cost(route: dict, travelers: int) -> int:
    if route.get("costCents") is not None:
        return int(route.get("costCents") or 0)
    mode = route.get("mode")
    distance_km = float(route.get("distanceM") or 0) / 1000.0
    if mode == "walking":
        return 0
    if mode == "transit":
        return 400 * max(1, travelers)
    return int((1000 + 250 * distance_km) * 1)


def _intercity(
    origin_center: Optional[Tuple[float, float]],
    destination_center: Tuple[float, float],
    preference: str,
    headcount: int,
) -> Dict:
    if not origin_center:
        return {
            "amountCents": 0,
            "mode": None,
            "distanceKm": 0,
            "note": "未填写出发地，城际交通暂未计入",
            "bookingUrl": "https://www.12306.cn/",
        }
    distance = haversine_km(origin_center, destination_center)
    if distance < 20:
        return {
            "amountCents": 0,
            "mode": "local",
            "distanceKm": round(distance, 1),
            "note": "出发地与目的地较近，未计城际交通",
            "bookingUrl": "https://www.12306.cn/",
        }
    mode = preference
    if mode == "auto":
        mode = "flight" if distance > 1200 else "rail"
    if mode == "flight":
        one_way = int((55 * distance + 30000))
        booking = "https://www.ctrip.com/"
        note = f"按约 {distance:.0f} km 的机票参考价估算（往返）"
    else:
        one_way = int(max(10000, 42 * distance))
        booking = "https://www.12306.cn/"
        note = f"按约 {distance:.0f} km 的高铁二等座参考价估算（往返）"
    amount = one_way * 2 * max(1, headcount)
    return {
        "amountCents": amount,
        "mode": mode,
        "distanceKm": round(distance, 1),
        "oneWayCents": one_way,
        "note": note,
        "bookingUrl": booking,
    }


def compute_budget(data: dict, origin_center: Optional[Tuple[float, float]]) -> dict:
    meta = data.get("meta") or {}
    travelers = meta.get("travelers") or {"adults": 2, "children": 0}
    adults = int(travelers.get("adults") or 1)
    children = int(travelers.get("children") or 0)
    headcount = max(1, adults + children)
    rooms = max(1, math.ceil(adults / 2))

    categories = {
        "ticket": {"label": "门票", "amountCents": 0},
        "hotel": {"label": "住宿", "amountCents": 0},
        "meal": {"label": "餐饮", "amountCents": 0},
        "local": {"label": "市内交通", "amountCents": 0},
        "intercity": {"label": "城际交通", "amountCents": 0},
    }
    day_amounts: Dict[int, int] = {}

    def add(tag: str, amount: int, day: int = 1) -> None:
        if amount <= 0:
            return
        categories[tag]["amountCents"] += amount
        day_amounts[day] = day_amounts.get(day, 0) + amount

    hotel_groups: Dict[str, dict] = {}
    for day in data.get("days") or []:
        day_index = int(day.get("dayIndex") or 1)
        for item in day.get("items") or []:
            cost = item.get("cost") or {}
            amount = int(cost.get("amountCents") or 0)
            item_type = item.get("type")
            if item_type == "hotel":
                key = item.get("poiId") or item.get("id")
                group = hotel_groups.setdefault(key, {"item": item, "nights": 0})
                group["nights"] += 1
                continue
            if item_type == "attraction":
                add("ticket", amount, day_index)
            elif item_type == "meal":
                add("meal", amount, day_index)
    for group in hotel_groups.values():
        item = group["item"]
        rate = int((item.get("cost") or {}).get("amountCents") or 0)
        nights = max(1, int(group["nights"]))
        total = rate * rooms * nights
        categories["hotel"]["amountCents"] += total
        # 酒店费用分摊到入住夜对应的日期（第一天起）
        for offset in range(nights):
            day_index = 1 + offset
            day_amounts[day_index] = day_amounts.get(day_index, 0) + rate * rooms

    for route in data.get("routes") or []:
        day_index = int(route.get("dayIndex") or 1)
        amount = _route_cost(route, headcount)
        route["costCents"] = amount
        add("local", amount, day_index)

    intercity = _intercity(
        origin_center=origin_center,
        destination_center=(
            float((data.get("destination") or {}).get("center", {}).get("lng", 104.0665)),
            float((data.get("destination") or {}).get("center", {}).get("lat", 30.5723)),
        ),
        preference=str(meta.get("transport", {}).get("intercity", "auto")),
        headcount=headcount,
    )
    categories["intercity"]["amountCents"] = intercity["amountCents"]
    if intercity["amountCents"]:
        day_amounts[1] = day_amounts.get(1, 0) + intercity["amountCents"]

    subtotal = sum(v["amountCents"] for v in categories.values())
    buffer_amount = int(round(subtotal * BUFFER_RATE))
    categories["buffer"] = {"label": "机动缓冲", "amountCents": buffer_amount}
    total = subtotal + buffer_amount

    # 每日预算：把缓冲按当天消费比例分摊，最后一天补齐尾差
    if buffer_amount:
        consumed = sum(day_amounts.values()) or 1
        allocated = 0
        days_sorted = sorted(day_amounts.keys())
        for idx, day_index in enumerate(days_sorted):
            if idx == len(days_sorted) - 1:
                share = buffer_amount - allocated
            else:
                share = int(round(buffer_amount * day_amounts[day_index] / consumed))
                allocated += share
            day_amounts[day_index] = day_amounts.get(day_index, 0) + share

    day_count = len(data.get("days") or [])
    daily = [
        {"dayIndex": i, "amountCents": day_amounts.get(i, 0)}
        for i in range(1, day_count + 1)
    ]
    budget_limit = int(meta.get("budgetLimitCents") or 0)
    notes = {
        "ticket": "按行程景点门票汇总",
        "hotel": f"{rooms} 间 × 实际入住晚数",
        "meal": "按人数与餐标估算",
        "local": "步行 / 公交 / 打车参考",
        "intercity": intercity["note"],
        "buffer": "价格波动与临时支出",
    }
    return {
        "totalCents": total,
        "perPersonCents": int(round(total / headcount)),
        "currency": "CNY",
        "bufferRate": BUFFER_RATE,
        "budgetLimitCents": budget_limit,
        "overBudget": bool(budget_limit and total > budget_limit),
        "categories": [
            {
                "key": key,
                "label": value["label"],
                "amountCents": value["amountCents"],
                "note": notes.get(key, ""),
            }
            for key, value in categories.items()
        ],
        "daily": daily,
        "transport": intercity,
        "priceNote": "门票、餐饮、酒店与交通均为参考估算，实际以商家/官方渠道为准。",
        "roomCount": rooms,
        "headcount": headcount,
    }
