from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    city: Mapped[str] = mapped_column(String(80), index=True)
    title: Mapped[str] = mapped_column(String(200))
    start_date: Mapped[str] = mapped_column(String(20))
    end_date: Mapped[str] = mapped_column(String(20))
    version: Mapped[int] = mapped_column(Integer, default=1)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class PlanRun(Base):
    __tablename__ = "plan_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    stage: Mapped[str] = mapped_column(String(40), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    request: Mapped[dict] = mapped_column(JSON)
    trip_id: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    events: Mapped[List[Any]] = mapped_column(JSON, default=list)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class ExportJob(Base):
    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    trip_id: Mapped[str] = mapped_column(String(40), index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True)
    format: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="queued")
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    media_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
