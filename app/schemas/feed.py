import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.feed import FeedPostType


class FeedPostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None
    type: FeedPostType
    payload: dict
    created_at: datetime
    reactions: dict[str, int] = Field(default_factory=dict)


class FeedShareRequest(BaseModel):
    message: str | None = Field(default=None, max_length=280)


class ReactionRequest(BaseModel):
    emoji: str = Field(min_length=1, max_length=16)
