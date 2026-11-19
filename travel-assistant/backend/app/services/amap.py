from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from typing import Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlencode

import httpx

from ..config import settings
from ..domain.models import Candidate

logger = logging.getLogger(__name__)
AMAP_BASE = "https://restapi.amap.com/v3"
_CACHE: Dict[str, Tuple[float, object]] = {}
_CACHE_TTL = 3600

DAY_COLORS = ["0x2563EB", "0xF97316", "0x0F766E", "0x7C3AED", "0xDB2777", "0x0891B2", "0xCA8A04"]


class AmapError(RuntimeError):
    pass


def _cache_get(key: str):
    item = _CACHE.get(key)
    if not item:
        return None
    ts, value = item
    if time.time() - ts > _CACHE_TTL:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_set(key: str, value) -> None:
    _CACHE[key] = (time.time(), value)


def _parse_location(value: str) -> Optional[Tuple[float, float]]:
    try:
        lng_s, lat_s = value.split(",")
        return float(lng_s), float(lat_s)
    except Exception:
        return None


def _safe_float(value, default: float = 0.0) -> float:
    try:
        if value in (None, "", "[]"):
            return default
        return float(value)
    except Exception:
        return default


def _area_from_address(address: str) -> str:
    match = re.search(r"([\u4e00-\u9fa5]{2,8}[区县市])", address or "")
    return match.group(1) if match else ""


def _clean_type(value: str) -> List[str]:
    parts = [p for p in re.split(r"[;|]", value or "") if p]
    generic = {
        "风景名胜", "公园广场", "餐饮服务", "住宿服务", "购物", "生活服务",
        "公司企业", "科教文化服务", "会展中心", "商务住宅", "地名地址信息",
        "交通设施服务", "购物相关", "体育休闲服务", "医疗保健服务",
    }
    return [p for p in parts if p not in generic][:4]


def _derived_tags(name: str) -> List[str]:
    tags: List[str] = []
    if any(k in name for k in ("湖", "山", "湿地", "江景", "河畔", "滨江", "海", "岛", "溪", "森林", "草原", "温泉", "瀑布")):
        tags.append("自然")
    if any(k in name for k in ("寺", "庙", "祠", "塔", "遗址", "古城", "古镇", "老街", "故居", "博物院", "博物馆", "纪念馆", "城墙")):
        tags.append("历史")
    if any(k in name for k in ("博物馆", "博物院", "展览馆", "美术馆", "科技馆")):
        tags.append("博物馆")
    if any(k in name for k in ("古镇", "古街", "老街", "巷", "街", "坊")):
        tags.append("街区")
    if any(k in name for k in ("乐园", "动物园", "亲子", "海洋馆", "水族馆")):
        tags.append("亲子")
    if any(k in name for k in ("夜景", "灯光", "夜市")):
        tags.append("夜景")
    return tags


class AmapClient:
    def __init__(self, key: Optional[str] = None):
        self.key = key or settings.amap_web_key_effective
        self._sem = asyncio.Semaphore(3)

    @property
    def configured(self) -> bool:
        return bool(self.key)

    async def _get(self, path: str, params: dict, timeout: float = 8.0) -> dict:
        if not self.key:
            raise AmapError("未配置高德 Web 服务 Key")
        query = dict(params)
        query["key"] = self.key
        cache_key = path + "?" + urlencode(sorted(query.items()))
        cached = _cache_get(cache_key)
        if cached is not None:
            return cached  # type: ignore[return-value]
        try:
            async with self._sem:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    resp = await client.get(AMAP_BASE + path, params=query)
                    resp.raise_for_status()
                    data = resp.json()
        except Exception as exc:
            raise AmapError(f"高德接口请求失败：{exc}") from exc
        if str(data.get("status")) != "1":
            raise AmapError(f"高德接口返回错误：{data.get('info') or data.get('infocode')}")
        _cache_set(cache_key, data)
        return data

    async def geocode(self, city: str) -> Optional[Tuple[float, float]]:
        if not self.configured:
            return None
        try:
            data = await self._get("/geocode/geo", {"address": city, "city": city})
            geocodes = data.get("geocodes") or []
            if not geocodes:
                return None
            return _parse_location(geocodes[0].get("location", ""))
        except Exception:
            return None

    async def search(
        self,
        city: str,
        keyword: str,
        kind: str,
        limit: int = 6,
        types: Optional[str] = None,
    ) -> List[Candidate]:
        if not self.configured:
            return []
        params = {
            "keywords": keyword,
            "city": city,
            "citylimit": "true",
            "offset": str(min(limit, 20)),
            "page": "1",
            "extensions": "all",
        }
        if types:
            params["types"] = types
        try:
            data = await self._get("/place/text", params)
        except AmapError as exc:
            logger.warning("amap place search failed: %s (%s)", keyword, exc)
            return []
        results = []
        for poi in data.get("pois") or []:
            loc = _parse_location(poi.get("location", ""))
            if not loc:
                continue
            name = (poi.get("name") or "").strip()
            if not name or any(bad in name for bad in ("停车场", "售票处", "入口", "厕所", "公交站")):
                continue
            lng, lat = loc
            address = poi.get("address") if isinstance(poi.get("address"), str) else city
            adname = poi.get("adname") if isinstance(poi.get("adname"), str) else ""
            biz = poi.get("biz_ext") or {}
            if not isinstance(biz, dict):
                biz = {}
            rating = _safe_float(biz.get("rating"), 4.4)
            raw_cost = _safe_float(biz.get("cost"), 0.0)
            if kind == "attraction":
                if raw_cost > 0:
                    cost = int(raw_cost * 100)
                    confidence = "medium"
                elif any(x in name for x in ("博物馆", "公园", "广场", "街区", "巷子", "古镇", "寺")):
                    cost = 0
                    confidence = "estimate"
                else:
                    cost = 5000
                    confidence = "estimate"
                cost_basis = "ticket"
                duration = 120
            elif kind == "meal":
                cost = int(raw_cost * 100) if raw_cost > 0 else 6000
                cost_basis = "person"
                duration = 60
                confidence = "medium" if raw_cost > 0 else "estimate"
            else:
                cost = int(raw_cost * 100) if raw_cost > 0 else 60000
                cost_basis = "room_night"
                duration = 30
                confidence = "medium" if raw_cost > 0 else "estimate"
            photos = poi.get("photos") or []
            image = None
            if photos and isinstance(photos, list) and isinstance(photos[0], dict):
                image = photos[0].get("url")
            tags = _clean_type(poi.get("type", ""))
            tags = list(dict.fromkeys(tags + _derived_tags(name)))
            if not tags:
                tags = [keyword]
            results.append(
                Candidate(
                    candidate_id="",
                    poi_id=str(poi.get("id") or f"amap-{abs(hash(name))}"),
                    name=name,
                    kind=kind,  # type: ignore[arg-type]
                    address=address if isinstance(address, str) else city,
                    lng=lng,
                    lat=lat,
                    rating=rating,
                    cost_cents=cost,
                    cost_basis=cost_basis,  # type: ignore[arg-type]
                    duration_min=duration,
                    tags=tags,
                    area=adname or _area_from_address(address if isinstance(address, str) else ""),
                    description=f"高德地图 POI · 评分 {rating:.1f}",
                    image=image if isinstance(image, str) else None,
                    source="amap",
                    confidence=confidence,
                    booking_url=f"https://www.amap.com/place/{poi.get('id')}",
                    open_hours=biz.get("open_time") if isinstance(biz.get("open_time"), str) else None,
                )
            )
        if not results and types:
            return await self.search(city, keyword, kind, limit=limit, types=None)
        return results

    async def search_many(self, city: str, kind: str, keywords: Sequence[str]) -> List[Candidate]:
        if not self.configured:
            return []
        types = {"attraction": "110000|140000", "meal": "050000", "hotel": "100000"}.get(kind)
        merged: Dict[str, Candidate] = {}
        # 高德个人 Key 的 QPS 较低，串行并在批次间留出间隔，避免并发触发限流后整类 POI 为空。
        for keyword in keywords:
            try:
                batch = await self.search(city, keyword, kind, limit=8, types=types)
            except Exception as exc:
                logger.warning("amap search_many failed: %s %s (%s)", kind, keyword, exc)
                batch = []
            for item in batch:
                merged.setdefault(item.poi_id, item)
            await asyncio.sleep(0.12)
        return list(merged.values())

    async def route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        mode: str,
        city: str,
    ) -> Optional[dict]:
        if not self.configured:
            return None
        origin_s = f"{origin[0]:.6f},{origin[1]:.6f}"
        dest_s = f"{destination[0]:.6f},{destination[1]:.6f}"
        try:
            if mode == "walking":
                data = await self._get(
                    "/direction/walking",
                    {"origin": origin_s, "destination": dest_s},
                    timeout=6,
                )
                paths = ((data.get("route") or {}).get("paths") or [])
            elif mode == "transit":
                data = await self._get(
                    "/direction/transit/integrated",
                    {
                        "origin": origin_s,
                        "destination": dest_s,
                        "city": city,
                        "cityd": city,
                        "strategy": "0",
                        "nightflag": "0",
                    },
                    timeout=8,
                )
                paths = ((data.get("route") or {}).get("transits") or [])
            else:
                data = await self._get(
                    "/direction/driving",
                    {"origin": origin_s, "destination": dest_s, "strategy": "0", "extensions": "base"},
                    timeout=8,
                )
                paths = ((data.get("route") or {}).get("paths") or [])
            if not paths:
                return None
            path = paths[0]
            distance = _safe_float(path.get("distance"), 0.0)
            duration = _safe_float(path.get("duration"), 0.0)
            points: List[List[float]] = []
            for step in path.get("steps") or []:
                polyline = step.get("polyline") or ""
                for pair in polyline.split(";"):
                    loc = _parse_location(pair)
                    if loc and (not points or points[-1] != [loc[0], loc[1]]):
                        points.append([loc[0], loc[1]])
            if len(points) < 2:
                points = [[origin[0], origin[1]], [destination[0], destination[1]]]
            return {
                "distanceM": int(distance),
                "durationMin": max(1, int(round(duration / 60))) if duration else 0,
                "polyline": points[:240],
                "status": "ok",
                "provider": "amap",
            }
        except Exception:
            return None

    def static_map_url(self, days: List[dict], route_legs: List[dict], center: dict) -> Optional[str]:
        if not self.configured:
            return None
        # 高德静态图单次最多支持少量标记，按天均匀取前 3 个，最多 9 个。
        per_day = max(1, 9 // max(1, len(days)))
        markers = []
        for day in days:
            color = DAY_COLORS[(day.get("dayIndex", 1) - 1) % len(DAY_COLORS)]
            items = sorted(
                day.get("items") or [],
                key=lambda item: 0 if item.get("type") == "attraction" else 1,
            )
            for idx, item in enumerate(items[:per_day]):
                loc = item.get("location") or {}
                if not loc.get("lng"):
                    continue
                label = str(idx + 1)
                markers.append(f"mid,{color},{label}:{loc['lng']:.6f},{loc['lat']:.6f}")
        if not markers:
            return None
        params = {
            "location": f"{center.get('lng', 104.0665):.6f},{center.get('lat', 30.5723):.6f}",
            "zoom": "11",
            "size": "1000*620",
            "scale": "2",
            "markers": "|".join(markers[:9]),
            "key": self.key,
        }
        # 静态图对 paths 参数较敏感，导出使用标记点版本；路线由时间轴和在线地图呈现。
        return "https://restapi.amap.com/v3/staticmap?" + urlencode(params)
