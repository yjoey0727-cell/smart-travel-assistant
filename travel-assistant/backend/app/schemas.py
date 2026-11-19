from __future__ import annotations

from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class Destination(ApiModel):
    city: str = Field(min_length=1, max_length=40)
    adcode: Optional[str] = None


class Travelers(ApiModel):
    adults: int = Field(default=2, ge=1, le=10)
    children: int = Field(default=0, ge=0, le=10)

    @property
    def total(self) -> int:
        return self.adults + self.children

    @property
    def billable_units(self) -> float:
        return self.adults + self.children * 0.5


class BudgetRequest(ApiModel):
    total_cents: int = Field(default=500000, ge=0, le=100000000)
    currency: str = "CNY"
    level: Literal["budget", "comfort", "premium"] = "comfort"


class Preferences(ApiModel):
    scenery: List[str] = Field(default_factory=list)
    food: List[str] = Field(default_factory=list)
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"
    hotel_level: Literal["budget", "comfort", "premium"] = "comfort"
    avoid: List[str] = Field(default_factory=list)


class Transport(ApiModel):
    intercity: Literal["auto", "rail", "flight"] = "auto"
    local: Literal["public", "taxi", "mixed"] = "mixed"


class PlanRequest(ApiModel):
    destination: Destination
    origin: Optional[str] = Field(default=None, max_length=40)
    start_date: date
    end_date: date
    travelers: Travelers = Field(default_factory=Travelers)
    budget: BudgetRequest = Field(default_factory=BudgetRequest)
    preferences: Preferences = Field(default_factory=Preferences)
    transport: Transport = Field(default_factory=Transport)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("origin")
    @classmethod
    def normalize_origin(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @model_validator(mode="after")
    def validate_dates(self) -> "PlanRequest":
        if self.end_date < self.start_date:
            raise ValueError("结束日期不能早于开始日期")
        days = (self.end_date - self.start_date).days + 1
        if days > 7:
            raise ValueError("单次行程最多支持 7 天")
        if self.travelers.total > 10:
            raise ValueError("同行人数最多 10 人")
        return self

    @property
    def day_count(self) -> int:
        return (self.end_date - self.start_date).days + 1


class PlanRunOut(ApiModel):
    run_id: str
    status: str = "queued"


class RunInfo(ApiModel):
    run_id: str
    status: str
    stage: str
    progress: int
    trip_id: Optional[str] = None
    error: Optional[str] = None


class PoiPayload(ApiModel):
    poi_id: str
    name: str
    type: Literal["attraction", "meal", "hotel"]
    address: str = ""
    lng: float
    lat: float
    rating: float = 4.5
    cost_cents: int = 0
    cost_basis: Literal["ticket", "person", "room_night"] = "person"
    duration_min: int = 90
    tags: List[str] = Field(default_factory=list)
    image: Optional[str] = None
    description: Optional[str] = None
    source: str = "amap"
    confidence: str = "estimate"
    booking_url: Optional[str] = None
    area: Optional[str] = None


class AddItemRequest(ApiModel):
    day_index: int = Field(ge=1, le=7)
    after_item_id: Optional[str] = None
    poi: PoiPayload


class UpdateItemRequest(ApiModel):
    day_index: Optional[int] = Field(default=None, ge=1, le=7)
    start_time: Optional[str] = None
    duration_min: Optional[int] = Field(default=None, ge=15, le=720)
    notes: Optional[str] = Field(default=None, max_length=500)
    locked: Optional[bool] = None

    @field_validator("start_time")
    @classmethod
    def validate_time(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        try:
            hour, minute = [int(x) for x in value.split(":")]
        except Exception:
            raise ValueError("时间格式应为 HH:mm")
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("时间格式应为 HH:mm")
        return f"{hour:02d}:{minute:02d}"


class ReorderRequest(ApiModel):
    item_ids: List[str]


class ExportRequest(ApiModel):
    format: Literal["pdf", "png"] = "pdf"


class TripSummary(ApiModel):
    id: str
    title: str
    city: str
    start_date: str
    end_date: str
    days: int
    total_cents: int
    cover: Optional[str] = None
    updated_at: Optional[str] = None
    version: int = 1


class SessionInfo(ApiModel):
    session_id: str
    demo_mode: bool
    amap_configured: bool
    llm_configured: bool
    demo_city: str
    export_ready: bool


class ExportOut(ApiModel):
    export_id: str
    status: str
    format: str
    download_url: Optional[str] = None
    error: Optional[str] = None
