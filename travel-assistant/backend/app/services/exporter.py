from __future__ import annotations

import asyncio
import base64
import html
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..config import settings
from ..db import SessionLocal
from ..models import ExportJob, Trip
from .amap import AmapClient

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = BASE_DIR / "templates"
env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

TYPE_LABEL = {"attraction": "景点", "meal": "餐饮", "hotel": "住宿", "transit": "交通"}


def _chrome_path() -> Optional[str]:
    candidates = [
        settings.chrome_bin,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _project(points: List[tuple], width: int, height: int):
    lngs = [p[0] for p in points]
    lats = [p[1] for p in points]
    min_lng, max_lng = min(lngs), max(lngs)
    min_lat, max_lat = min(lats), max(lats)
    pad = 42
    span_lng = max(0.002, max_lng - min_lng)
    span_lat = max(0.002, max_lat - min_lat)
    scale = min((width - pad * 2) / span_lng, (height - pad * 2) / span_lat)
    offset_x = (width - span_lng * scale) / 2
    offset_y = (height - span_lat * scale) / 2

    def fn(lng: float, lat: float):
        x = offset_x + (lng - min_lng) * scale
        y = height - offset_y - (lat - min_lat) * scale
        return x, y

    return fn


def build_map_svg(days: List[dict], routes: List[dict], width: int = 1000, height: int = 380, show_labels: bool = True, dedupe: bool = False) -> str:
    day_items = []
    seen_pois = set()
    for day in days:
        for idx, item in enumerate(day.get("items") or []):
            loc = item.get("location") or {}
            if loc.get("lng") is None:
                continue
            if dedupe and item.get("poiId") in seen_pois:
                continue
            seen_pois.add(item.get("poiId"))
            day_items.append((day, idx + 1, item, float(loc["lng"]), float(loc["lat"])))
    if not day_items:
        return (
            f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
            f'style="width:100%;height:auto;background:#f8fafc">'
            f'<text x="{width/2}" y="{height/2}" text-anchor="middle" fill="#94a3b8" '
            f'font-size="16">暂无坐标数据</text></svg>'
        )
    points = [(p[3], p[4]) for p in day_items]
    project = _project(points, width, height)
    projected = {item.get("id"): project(lng, lat) for _day, _num, item, lng, lat in day_items}
    parts = [
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" '
        f'style="width:100%;height:auto;display:block;background:#f8fafc">',
        f'<rect width="{width}" height="{height}" fill="#f8fafc"/>',
    ]
    # 轻量网格，模拟地图底图
    for i in range(1, 8):
        x = width * i / 8
        parts.append(f'<line x1="{x:.1f}" y1="0" x2="{x:.1f}" y2="{height}" stroke="#e2e8f0" stroke-width="1"/>')
    for i in range(1, 5):
        y = height * i / 5
        parts.append(f'<line x1="0" y1="{y:.1f}" x2="{width}" y2="{y:.1f}" stroke="#e2e8f0" stroke-width="1"/>')
    parts.append(
        f'<path d="M0 {height*0.72:.1f} C {width*0.22:.1f} {height*0.61:.1f}, '
        f'{width*0.36:.1f} {height*0.83:.1f}, {width*0.56:.1f} {height*0.72:.1f} '
        f'S {width*0.82:.1f} {height*0.58:.1f}, {width} {height*0.66:.1f}" '
        f'fill="none" stroke="#dbeafe" stroke-width="18" stroke-linecap="round" opacity="0.8"/>'
    )
    colors = {int(d.get("dayIndex") or 1): d.get("color") or "#2563eb" for d in days}
    for route in routes:
        points_route = route.get("polyline") or []
        if len(points_route) < 2:
            continue
        coords = " ".join(
            f"{project(float(p[0]), float(p[1]))[0]:.1f},{project(float(p[0]), float(p[1]))[1]:.1f}"
            for p in points_route[:100]
        )
        color = colors.get(int(route.get("dayIndex") or 1), "#2563eb")
        parts.append(
            f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="3.5" '
            f'stroke-linecap="round" stroke-linejoin="round" opacity="0.78"/>'
        )
    for day, number, item, lng, lat in day_items:
        x, y = projected[item.get("id")]
        color = day.get("color") or "#2563eb"
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="13" fill="{color}" stroke="#fff" stroke-width="3"/>')
        parts.append(
            f'<text x="{x:.1f}" y="{y+4.5:.1f}" text-anchor="middle" fill="#fff" '
            f'font-size="11" font-weight="700">{number}</text>'
        )
        if show_labels:
            # 与相邻标记距离过近时不画文字，避免地图标签互相压盖。
            others = [
                ((x - ox) ** 2 + (y - oy) ** 2) ** 0.5
                for iid, (ox, oy) in projected.items()
                if iid != item.get("id")
            ]
            if not others or min(others) >= 48:
                title = html.escape(str(item.get("title") or "")[:10])
                if number % 2 == 0:
                    tx, anchor = x - 18, "end"
                else:
                    tx, anchor = x + 18, "start"
                parts.append(
                    f'<text x="{tx:.1f}" y="{y+4:.1f}" fill="#334155" font-size="10" '
                    f'text-anchor="{anchor}" font-weight="500">{title}</text>'
                )
    parts.append(
        f'<text x="18" y="28" fill="#0f172a" font-size="13" font-weight="600">'
        f'{html.escape(str(days[0].get("date") if days else ""))} · 路线示意</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _day_stats(trip: dict) -> dict:
    attractions = meals = hotels = 0
    for day in trip.get("days") or []:
        for item in day.get("items") or []:
            if item.get("type") == "attraction":
                attractions += 1
            elif item.get("type") == "meal":
                meals += 1
            elif item.get("type") == "hotel":
                hotels += 1
    return {"attractions": attractions, "meals": meals, "hotels": hotels}


def render_export_html(trip: dict, amap: Optional[AmapClient] = None, map_image_uri: Optional[str] = None) -> str:
    days = []
    for idx, day in enumerate(trip.get("days") or []):
        color = ["#2563eb", "#f97316", "#0f766e", "#7c3aed", "#db2777", "#0891b2", "#ca8a04"][idx % 7]
        copy = dict(day)
        copy["color"] = color
        copy["map_svg"] = build_map_svg(
            [copy],
            [r for r in trip.get("routes") or [] if int(r.get("dayIndex") or 0) == int(day.get("dayIndex") or 0)],
            show_labels=len(day.get("items") or []) <= 5,
        )
        copy["items"] = [
            {**item, "typeLabel": TYPE_LABEL.get(item.get("type"), "安排")}
            for item in day.get("items") or []
        ]
        days.append(copy)
    map_svg = build_map_svg(days, trip.get("routes") or [], show_labels=False, dedupe=True)
    map_url = map_image_uri
    template = env.get_template("export.html")
    return template.render(
        trip={**trip, "days": days},
        days=days,
        stats=_day_stats(trip),
        map_svg=map_svg,
        map_url=map_url,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )


def _run_chrome(chrome: str, args: List[str], timeout: int = 70) -> subprocess.CompletedProcess:
    cmd = [
        chrome,
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--hide-scrollbars",
        "--no-first-run",
        "--no-default-browser-check",
    ] + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


async def _update_job(job_id: str, **values) -> None:
    async with SessionLocal() as db:
        job = await db.get(ExportJob, job_id)
        if not job:
            return
        for key, value in values.items():
            setattr(job, key, value)
        await db.commit()


async def process_export(job_id: str, trip_data: dict, fmt: str) -> None:
    await _update_job(job_id, status="running")
    from ..domain.budget import compute_budget

    origin = (trip_data.get("meta") or {}).get("originCenter") or None
    origin_center = (float(origin["lng"]), float(origin["lat"])) if origin else None
    trip_data = {**trip_data, "budget": compute_budget(trip_data, origin_center)}
    out_dir = settings.data_dir / "exports"
    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / f"{job_id}.html"
    try:
        amap = AmapClient()
        map_image_uri = None
        if amap.configured:
            try:
                # 静态地图由服务端下载后内嵌为 data URI，避免把 Web 服务 Key 写进导出 HTML/PDF。
                map_url = amap.static_map_url(
                    trip_data.get("days") or [],
                    trip_data.get("routes") or [],
                    (trip_data.get("destination") or {}).get("center") or {},
                )
                if map_url:
                    async with httpx.AsyncClient(timeout=20) as client:
                        resp = await client.get(map_url)
                        content_type = resp.headers.get("content-type", "image/png").split(";")[0]
                        if resp.status_code == 200 and content_type.startswith("image/"):
                            encoded = base64.b64encode(resp.content).decode("ascii")
                            map_image_uri = f"data:{content_type};base64,{encoded}"
            except Exception:
                map_image_uri = None
        rendered = render_export_html(trip_data, amap, map_image_uri)
        html_path.write_text(rendered, encoding="utf-8")
        chrome = _chrome_path()
        if not chrome:
            await _update_job(
                job_id,
                status="succeeded",
                file_path=str(html_path),
                media_type="text/html; charset=utf-8",
                error="当前环境未找到 Chrome，已生成可打印 HTML；用浏览器打开后可另存为 PDF。",
            )
            return

        profile = Path(tempfile.mkdtemp(prefix="ta-chrome-", dir=str(settings.data_dir)))
        try:
            if fmt == "pdf":
                out_path = out_dir / f"{job_id}.pdf"
                result = await asyncio.to_thread(
                    _run_chrome,
                    chrome,
                    [
                        f"--user-data-dir={profile}",
                        "--no-pdf-header-footer",
                        "--print-to-pdf-no-header",
                        "--virtual-time-budget=8000",
                        f"--print-to-pdf={out_path}",
                        html_path.as_uri(),
                    ],
                )
                if not out_path.exists() or out_path.stat().st_size < 1000:
                    raise RuntimeError((result.stderr or "PDF 生成失败")[-300:])
                await _update_job(
                    job_id,
                    status="succeeded",
                    file_path=str(out_path),
                    media_type="application/pdf",
                    error=None,
                )
            else:
                out_path = out_dir / f"{job_id}.png"
                # 封面 + 总览 + 每天约 1200px；留出余量避免长图被截断。
                height = min(12000, max(2600, 2000 + len(trip_data.get("days") or []) * 1200))
                scale = 2 if height * 2 <= 14000 else 1
                result = await asyncio.to_thread(
                    _run_chrome,
                    chrome,
                    [
                        f"--user-data-dir={profile}",
                        f"--force-device-scale-factor={scale}",
                        f"--window-size=1240,{height}",
                        "--virtual-time-budget=8000",
                        f"--screenshot={out_path}",
                        html_path.as_uri(),
                    ],
                )
                if not out_path.exists() or out_path.stat().st_size < 1000:
                    raise RuntimeError((result.stderr or "PNG 生成失败")[-300:])
                await _update_job(
                    job_id,
                    status="succeeded",
                    file_path=str(out_path),
                    media_type="image/png",
                    error=None,
                )
        finally:
            shutil.rmtree(profile, ignore_errors=True)
    except Exception as exc:
        # 浏览器渲染失败时保留可打印 HTML，保证演示仍能分享
        if html_path.exists():
            await _update_job(
                job_id,
                status="succeeded",
                file_path=str(html_path),
                media_type="text/html; charset=utf-8",
                error=f"PDF/PNG 渲染失败，已生成可打印 HTML：{exc}",
            )
        else:
            await _update_job(job_id, status="failed", error=str(exc))
