import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    DateTime,
    Date,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class StepSource(str, enum.Enum):
    SENSOR = "sensor"
    MANUAL = "manual"


class StepEvent(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "step_events"
    __table_args__ = (
        UniqueConstraint("user_id", "client_event_id", name="uq_step_events_user_client_event"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    client_event_id: Mapped[str] = mapped_column(String(100), nullable=False)
    steps_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[StepSource] = mapped_column(Enum(StepSource, name="step_source"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DailyStat(UUIDPkMixin, Base):
    __tablename__ = "daily_stats"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_stats_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    total_steps: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    distance_km: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    calories: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    goal_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
