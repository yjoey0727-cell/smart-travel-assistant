from __future__ import annotations

import json
import logging
from typing import List, Optional

import httpx

from ..config import settings
from ..domain.models import Candidate

logger = logging.getLogger(__name__)


def _candidate_lines(candidates: List[Candidate]) -> str:
    buckets = {
        "attraction": [c for c in candidates if c.kind == "attraction"][:15],
        "meal": [c for c in candidates if c.kind == "meal"][:12],
        "hotel": [c for c in candidates if c.kind == "hotel"][:8],
    }
    label = {"attraction": "景点", "meal": "餐饮", "hotel": "酒店"}
    lines = []
    for kind in ("attraction", "meal", "hotel"):
        for c in buckets[kind]:
            price = f"¥{c.cost_cents / 100:.0f}"
            unit = {"attraction": "/人", "meal": "/人", "hotel": "/间夜"}[kind]
            tags = ",".join(c.tags[:3])
            lines.append(
                f"[{label[kind]}] {c.candidate_id} | {c.name} | 评分{c.rating:.1f} | "
                f"{price}{unit} | {c.duration_min}分钟 | {tags} | {c.area or c.address}"
            )
    return "\n".join(lines)


def _extract_json(text: str) -> Optional[dict]:
    text = (text or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except Exception:
        return None


async def generate_plan_payload(request: dict, candidates: List[Candidate]) -> Optional[dict]:
    if not settings.llm_configured:
        return None
    prefs = request.get("preferences") or {}
    travelers = request.get("travelers") or {}
    budget = request.get("budget") or {}
    destination = request.get("destination") or {}
    day_count = int(request["_day_count"])
    candidate_text = _candidate_lines(candidates)

    system = (
        "你是资深国内旅行规划师。你只能从给定的候选 POI 中选择，不能编造景点、餐厅、酒店，"
        "也不能编造坐标、票价或营业时间。输出必须是合法 JSON，不要输出 Markdown 代码块。"
    )
    user = f"""请为下面这次旅行生成按天行程。

目的地：{destination.get('city')}
日期：{request.get('startDate')} 至 {request.get('endDate')}，共 {day_count} 天
人数：成人 {travelers.get('adults')} 人，儿童 {travelers.get('children')} 人
预算：约 ¥{int(budget.get('totalCents') or 0) / 100:.0f}
节奏：{prefs.get('pace')}
偏好风景：{', '.join(prefs.get('scenery') or []) or '无特别偏好'}
偏好美食：{', '.join(prefs.get('food') or []) or '无特别偏好'}
酒店档位：{prefs.get('hotelLevel') or prefs.get('hotel_level') or 'comfort'}
避开：{', '.join(prefs.get('avoid') or []) or '无'}
补充：{request.get('notes') or '无'}

候选 POI（只能使用方括号中的候选 ID）：
{candidate_text}

规则：
1. 每天 2-4 个景点（按节奏调整），午餐和晚餐各 1 个餐饮候选。
2. 除最后一天外，每天安排 1 个酒店候选作为当天最后一项；最后一天不要安排酒店。
3. 时间要合理，避免同一时间重叠；一天不要排得太满。
4. 景点尽量按地理位置就近安排，减少折返。
5. 只输出 JSON，结构如下：
{{
  "days": [
    {{
      "dayIndex": 1,
      "theme": "当天主题，12字以内",
      "summary": "一句话说明",
      "items": [
        {{"candidateId": "a1", "startTime": "09:00", "durationMin": 120, "note": "简短提示"}}
      ]
    }}
  ],
  "rationale": "整体思路，80字以内"
}}
"""
    base = settings.llm_base_url.rstrip("/")
    url = base + "/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "max_tokens": 4000,
    }
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        content = ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
        parsed = _extract_json(content)
        if not parsed:
            logger.warning("LLM returned non-JSON content")
        return parsed
    except Exception as exc:
        logger.warning("LLM planning failed: %s", exc)
        return None
