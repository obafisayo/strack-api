import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class FriendshipStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"


class Friendship(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("requester_id", "addressee_id", name="uq_friendships_requester_addressee"),
        CheckConstraint("requester_id != addressee_id", name="ck_friendships_no_self_friend"),
    )

    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[FriendshipStatus] = mapped_column(
        Enum(FriendshipStatus, name="friendship_status"),
        default=FriendshipStatus.PENDING,
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FriendGoalStatus(str, enum.Enum):
    ACTIVE = "active"
    BROKEN = "broken"
    COMPLETED = "completed"


class FriendGoal(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "friend_goals"
    __table_args__ = (
        CheckConstraint("user_a_id != user_b_id", name="ck_friend_goals_distinct_users"),
    )

    user_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[FriendGoalStatus] = mapped_column(
        Enum(FriendGoalStatus, name="friend_goal_status"),
        default=FriendGoalStatus.ACTIVE,
        nullable=False,
    )
    mutual_streak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
