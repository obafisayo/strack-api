import uuid
from enum import Enum

from pydantic import BaseModel


class LeaderboardScope(str, Enum):
    TODAY = "today"
    WEEK = "week"
    MONTH = "month"


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: uuid.UUID
    display_name: str
    avatar_url: str | None
    steps: int
    is_self: bool


class LeaderboardResponse(BaseModel):
    scope: LeaderboardScope
    my_rank: int | None
    entries: list[LeaderboardEntry]
