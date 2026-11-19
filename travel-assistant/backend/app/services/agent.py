from __future__ import annotations

import logging
from typing import Awaitable, Callable, List, Optional, Tuple

from ..domain import seed
from ..domain.models import Candidate
from ..domain.planner import build_llm_plan, build_rule_plan
from ..schemas import PlanRequest
from .amap import AmapClient
from .llm import generate_plan_payload
from .trip_service import finalize_trip, materialize_trip, resolve_origin_center

logger = logging.getLogger(__name__)

Emit = Callable[[dict], Awaitable[None]]


class PlanningError(RuntimeError):
    pass


def _assign_ids(candidates: List[Candidate]) -> List[Candidate]:
    prefixes = {"attraction": "a", "meal": "f", "hotel": "h"}
    counters = {"attraction": 0, "meal": 0, "hotel": 0}
    result = []
    seen = set()
    for candidate in candidates:
        if candidate.poi_id in seen:
            continue
        seen.add(candidate.poi_id)
        counters[candidate.kind] += 1
        candidate.candidate_id = f"{prefixes[candidate.kind]}{counters[candidate.kind]}"
        result.append(candidate)
    return result


async def gather_candidates(amap: AmapClient, city: str, preferences: Optional[dict] = None) -> Tuple[List[Candidate], str]:
    if amap.configured:
        attraction_groups, meal_groups, hotel_groups = await _gather_amap(amap, city, preferences or {})
    else:
        if city != "成都":
            raise PlanningError(
                f"当前是内置演示模式，只内置了成都的示例数据。请在后端 .env 配置 AMAP_WEB_KEY 后再规划「{city}」。"
            )
        return seed.seed_candidates(city), "seed"

    attractions = _assign_ids(attraction_groups)
    meals = _assign_ids(meal_groups)
    hotels = _assign_ids(hotel_groups)
    combined = _assign_ids(attractions + meals + hotels)
    if len([c for c in combined if c.kind == "attraction"]) < 1:
        if city == "成都":
            fallback = seed.seed_candidates(city)
            return _assign_ids(fallback), "seed-fallback"
        raise PlanningError(
            "高德没有检索到足够的景点，请换一个城市名或稍后重试；也可以在 .env 中检查 AMAP_WEB_KEY 是否有效。"
        )
    return combined, "amap"


async def _gather_amap(amap: AmapClient, city: str, preferences: dict):
    import asyncio

    bad_names = (
        "国际博览中心", "国际会议中心", "市民中心", "行政服务中心", "停车场",
        "售票处", "入口", "厕所", "公交站", "地铁站", "写字楼", "产业园",
        "风景名胜区-",
    )
    highlights = seed.CITY_HIGHLIGHTS.get(city, [])[:6]
    merged: dict = {}
    highlight_ids = set()

    # 先按“城市必去”关键词逐个取最相关的一条，避免西湖断桥/苏堤等子景点挤满候选池。
    for rank, keyword in enumerate(highlights):
        try:
            batch = await amap.search(city, keyword, "attraction", limit=1)
        except Exception:
            batch = []
        for item in batch:
            item.tags = list(dict.fromkeys(item.tags + ["必去"]))
            item.priority = max(item.priority, 30 - rank * 3)
            if item.poi_id in merged:
                merged[item.poi_id].priority = max(merged[item.poi_id].priority, item.priority)
                merged[item.poi_id].tags = list(dict.fromkeys(merged[item.poi_id].tags + item.tags))
            else:
                merged[item.poi_id] = item
            highlight_ids.add(item.poi_id)
        await asyncio.sleep(0.12)

    generic_queries = ["5A景区", "博物馆", "古镇", "公园"] if highlights else [f"{city}景点", "5A景区", "博物馆", "古镇"]
    generic = await amap.search_many(city, "attraction", generic_queries)
    for item in generic:
        if any(bad in item.name for bad in bad_names):
            continue
        if any(keyword in item.name for keyword in highlights) and item.poi_id not in highlight_ids:
            # 必去关键词已经有一条主结果，跳过同名的子景点/重复结果。
            continue
        merged.setdefault(item.poi_id, item)

    attractions = list(merged.values())
    attractions = [item for item in attractions if not any(bad in item.name for bad in bad_names)]
    attractions = sorted(
        attractions,
        key=lambda c: (1 if "必去" in c.tags else 0, c.rating),
        reverse=True,
    )[:22]

    food_queries = []
    for source in [preferences.get("food") or [], seed.CITY_FOOD.get(city, []), ["小吃"]]:
        for keyword in source:
            keyword = str(keyword).strip()
            if keyword and keyword not in food_queries:
                food_queries.append(keyword)
    food_queries = food_queries[:5]

    meals = await amap.search_many(city, "meal", food_queries)
    if not meals:
        await asyncio.sleep(0.8)
        meals = await amap.search_many(city, "meal", food_queries[:2] or ["小吃"])
    hotels = await amap.search_many(city, "hotel", ["酒店", "民宿"])
    if not hotels:
        await asyncio.sleep(0.8)
        hotels = await amap.search_many(city, "hotel", ["酒店"])

    shopping = ("购物", "商场", "广场", "银泰", "来福士", "D11", "大厦")
    food_words = ("餐", "饭", "火锅", "面", "粉", "饺", "小吃", "咖啡", "茶", "烧烤", "串", "菜", "店", "馆")
    meals = [
        item for item in meals
        if not (any(word in item.name for word in shopping) and not any(word in item.name for word in food_words))
    ]
    meals = sorted(meals, key=lambda c: c.rating, reverse=True)[:16]
    hotels = sorted(hotels, key=lambda c: c.rating, reverse=True)[:8]
    return attractions, meals, hotels


class PlanningAgent:
    def __init__(self, amap: Optional[AmapClient] = None):
        self.amap = amap or AmapClient()

    async def run(self, request: PlanRequest, emit: Emit) -> dict:
        city = request.destination.city
        await emit(
            {
                "type": "stage",
                "stage": "normalize",
                "progress": 8,
                "message": "正在读取日期、人数与偏好",
            }
        )
        center = await self.amap.geocode(city) if self.amap.configured else None
        if not center:
            center = seed.city_center(city)
        origin_center = await resolve_origin_center(self.amap, request.origin)
        request_data = request.model_dump(by_alias=True)

        await emit(
            {
                "type": "stage",
                "stage": "gather",
                "progress": 28,
                "message": "正在检索景点、餐饮与酒店",
            }
        )
        candidates, source = await gather_candidates(
            self.amap, city, request_data.get("preferences") or {}
        )
        if not candidates:
            raise PlanningError("没有找到可用 POI，请检查城市名或高德 Key。")
        counts = {
            "attraction": len([c for c in candidates if c.kind == "attraction"]),
            "meal": len([c for c in candidates if c.kind == "meal"]),
            "hotel": len([c for c in candidates if c.kind == "hotel"]),
        }

        request_data["_day_count"] = request.day_count
        await emit(
            {
                "type": "stage",
                "stage": "draft",
                "progress": 48,
                "message": "正在按天编排行程与用餐",
            }
        )

        planner = "rule"
        rationale = ""
        payload = None
        if self.amap.configured and source == "amap":
            # 只有真实 POI 才调用 LLM；演示数据直接走规则，保证可复现。
            payload = await generate_plan_payload(request_data, candidates)
        if payload:
            try:
                draft = build_llm_plan(payload, candidates, request_data, center, planner_name="llm")
                if draft.get("days"):
                    planner = "llm"
                    rationale = draft.get("rationale", "")
            except Exception as exc:
                logger.warning("parse llm plan failed: %s", exc)
                draft = build_rule_plan(candidates, request_data, center)
                planner = "rule-fallback"
        else:
            draft = build_rule_plan(candidates, request_data, center)
            planner = "rule"
        draft["rationale"] = rationale or draft.get("rationale", "")

        total_items = sum(len(day.get("items") or []) for day in draft.get("days") or [])
        if total_items == 0:
            raise PlanningError("未能生成有效行程，请检查目的地或偏好设置。")

        meta_extra = {
            "demo": not (self.amap.configured and source == "amap"),
            "amap": self.amap.configured and source == "amap",
            "llm": planner == "llm",
        }
        trip = materialize_trip(
            request=request,
            draft=draft,
            center=center,
            origin_center=origin_center,
            adcode=(seed.CITY_PROFILES.get(city) or {}).get("adcode"),
            meta_extra=meta_extra,
        )
        trip["meta"]["planner"] = planner
        trip["meta"]["candidateSource"] = source
        trip["meta"]["candidateCounts"] = counts
        trip["meta"]["reason"] = draft.get("rationale", "")

        await emit(
            {
                "type": "stage",
                "stage": "route",
                "progress": 70,
                "message": "正在计算路线与交通时间",
            }
        )
        trip = await finalize_trip(trip, self.amap, origin_center)
        await emit(
            {
                "type": "stage",
                "stage": "budget",
                "progress": 90,
                "message": "正在汇总预算",
            }
        )
        await emit(
            {
                "type": "day",
                "days": [
                    {
                        "dayIndex": d["dayIndex"],
                        "date": d["date"],
                        "theme": d["theme"],
                        "summary": d["summary"],
                        "items": d["items"],
                    }
                    for d in trip["days"]
                ],
            }
        )
        return trip
