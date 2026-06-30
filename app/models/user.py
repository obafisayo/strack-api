import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.settings import UserSettings
    from app.models.streaks import Streak


class AgeGroup(str, enum.Enum):
    UNDER_18 = "under_18"
    AGE_18_40 = "18_40"
    AGE_41_65 = "41_65"
    AGE_65_PLUS = "65_plus"


class ActivityLevel(str, enum.Enum):
    SEDENTARY = "sedentary"
    LIGHTLY_ACTIVE = "lightly_active"
    ACTIVE = "active"


class Gender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class User(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    google_sub: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )

    preferred_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gender: Mapped[Gender | None] = mapped_column(Enum(Gender, name="gender"), nullable=True)
    age_group: Mapped[AgeGroup | None] = mapped_column(
        Enum(AgeGroup, name="age_group"), nullable=True
    )
    activity_level: Mapped[ActivityLevel | None] = mapped_column(
        Enum(ActivityLevel, name="activity_level"), nullable=True
    )
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    onboarding_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    streak: Mapped["Streak"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
