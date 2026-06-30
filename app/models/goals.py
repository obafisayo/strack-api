import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class DailyGoal(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "daily_goals"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_goals_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    goal_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    baseline_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    is_manual_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
