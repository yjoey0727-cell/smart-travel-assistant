from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class Candidate(BaseModel):
    candidate_id: str
    poi_id: str
    name: str
    kind: Literal["attraction", "meal", "hotel"]
    address: str = ""
    lng: float
    lat: float
    rating: float = 4.5
    cost_cents: int = 0
    cost_basis: Literal["ticket", "person", "room_night"] = "person"
    duration_min: int = 90
    tags: List[str] = Field(default_factory=list)
    area: str = ""
    description: str = ""
    image: Optional[str] = None
    source: str = "seed"
    confidence: str = "estimate"
    booking_url: Optional[str] = None
    open_hours: Optional[str] = None
    priority: int = 0

    def to_public(self) -> dict:
        return {
            "poiId": self.poi_id,
            "name": self.name,
            "type": self.kind,
            "address": self.address,
            "lng": self.lng,
            "lat": self.lat,
            "rating": self.rating,
            "costCents": self.cost_cents,
            "costBasis": self.cost_basis,
            "durationMin": self.duration_min,
            "tags": self.tags,
            "image": self.image,
            "description": self.description,
            "source": self.source,
            "confidence": self.confidence,
            "bookingUrl": self.booking_url,
            "area": self.area,
        }
