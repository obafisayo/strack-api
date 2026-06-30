import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import ActivityLevel, AgeGroup, Gender


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    username: str
    preferred_name: str | None
    gender: Gender | None
    age_group: AgeGroup | None
    activity_level: ActivityLevel | None
    avatar_url: str | None
    created_at: datetime
    onboarding_completed_at: datetime | None


class UserUpdate(BaseModel):
    username: str | None = None
    preferred_name: str | None = None
    gender: Gender | None = None
    avatar_url: str | None = None


class UserStats(BaseModel):
    total_steps: int
    best_day_steps: int
    longest_streak: int
    friend_count: int
