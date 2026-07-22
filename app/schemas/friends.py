import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.friends import FriendGoalStatus, FriendshipStatus


class FriendRequestCreate(BaseModel):
    username_or_email: str | None = Field(default=None, min_length=1)
    user_id: uuid.UUID | None = None

    @model_validator(mode="after")
    def _require_one_identifier(self) -> "FriendRequestCreate":
        if not self.username_or_email and not self.user_id:
            raise ValueError("Provide either username_or_email or user_id")
        return self


class FriendRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    requester_id: uuid.UUID
    addressee_id: uuid.UUID
    status: FriendshipStatus
    created_at: datetime
    display_name: str | None = None
    avatar_url: str | None = None


class FriendRead(BaseModel):
    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None
    friends_since: datetime


class FriendSuggestion(BaseModel):
    user_id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None


class InviteLinkResponse(BaseModel):
    invite_code: str
    invite_url: str


class FriendGoalCreate(BaseModel):
    friend_user_id: uuid.UUID
    target_steps: int = Field(gt=0, le=100_000)
    start_date: date


class FriendGoalUpdate(BaseModel):
    status: FriendGoalStatus | None = None
    target_steps: int | None = Field(default=None, gt=0, le=100_000)


class FriendGoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_a_id: uuid.UUID
    user_b_id: uuid.UUID
    target_steps: int
    start_date: date
    status: FriendGoalStatus
    mutual_streak_count: int
