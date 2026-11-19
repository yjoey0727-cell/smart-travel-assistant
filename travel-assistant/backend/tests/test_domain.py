from __future__ import annotations

from app.domain.budget import compute_budget
from app.domain.planner import build_rule_plan
from app.domain.seed import seed_candidates


def _trip_fixture():
    return {
        "destination": {"city": "成都", "center": {"lng": 104.0665, "lat": 30.5723}},
        "days": [
            {
                "dayIndex": 1,
                "date": "2026-11-01",
                "theme": "市区",
                "items": [
                    {
                        "id": "i1",
                        "type": "attraction",
                        "poiId": "p1",
                        "title": "武侯祠",
                        "location": {"lng": 104.0431, "lat": 30.6424},
                        "cost": {"amountCents": 10000},
                    },
                    {
                        "id": "i2",
                        "type": "meal",
                        "poiId": "p2",
                        "title": "午餐",
                        "location": {"lng": 104.045, "lat": 30.642},
                        "cost": {"amountCents": 12000},
                    },
                    {
                        "id": "h1",
                        "type": "hotel",
                        "poiId": "hotel",
                        "title": "酒店",
                        "location": {"lng": 104.079, "lat": 30.656},
                        "cost": {"amountCents": 65000},
                    },
                ],
            },
            {
                "dayIndex": 2,
                "date": "2026-11-02",
                "theme": "市区",
                "items": [
                    {
                        "id": "i3",
                        "type": "attraction",
                        "poiId": "p3",
                        "title": "宽窄巷子",
                        "location": {"lng": 104.0553, "lat": 30.6696},
                        "cost": {"amountCents": 0},
                    },
                    {
                        "id": "h2",
                        "type": "hotel",
                        "poiId": "hotel",
                        "title": "酒店",
                        "location": {"lng": 104.079, "lat": 30.656},
                        "cost": {"amountCents": 65000},
                    },
                ],
            },
        ],
        "routes": [
            {
                "dayIndex": 1,
                "fromItemId": "i1",
                "toItemId": "i2",
                "mode": "walking",
                "distanceM": 500,
                "durationMin": 8,
            }
        ],
        "meta": {
            "travelers": {"adults": 2, "children": 0},
            "transport": {"intercity": "auto"},
            "budgetLimitCents": 800000,
        },
    }


def test_budget_deduplicates_hotel_nights():
    budget = compute_budget(_trip_fixture(), (116.4074, 39.9042))
    assert budget["totalCents"] > 0
    categories = {c["key"]: c for c in budget["categories"]}
    assert categories["ticket"]["amountCents"] == 10000
    assert categories["meal"]["amountCents"] == 12000
    # 同一酒店两晚，1 间房：650 * 2
    assert categories["hotel"]["amountCents"] == 130000
    assert categories["intercity"]["amountCents"] > 0
    assert "note" in categories["hotel"]


def test_rule_plan_is_geographically_sane():
    candidates = seed_candidates("成都")
    request = {
        "preferences": {
            "scenery": ["历史", "自然"],
            "food": ["川菜"],
            "pace": "balanced",
            "hotelLevel": "comfort",
            "avoid": [],
        },
        "travelers": {"adults": 2, "children": 0},
        "_day_count": 3,
    }
    plan = build_rule_plan(candidates, request, (104.0665, 30.5723))
    assert len(plan["days"]) == 3
    assert plan["planner"] == "rule"
    for day in plan["days"]:
        assert day["items"], "每天至少有一个安排"
        assert any(spec["candidate"].kind == "attraction" for spec in day["items"])
    last_day = plan["days"][-1]
    assert not any(spec["candidate"].kind == "hotel" for spec in last_day["items"])
    names = {
        spec["candidate"].name
        for day in plan["days"]
        for spec in day["items"]
        if spec["candidate"].kind == "attraction"
    }
    assert "都江堰景区" not in names
    assert "青城山" not in names
