import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.steps import StepSource


class StepEventIn(BaseModel):
    client_event_id: str = Field(max_length=100)
    steps_delta: int = Field(gt=0, le=100_000)
    recorded_at: datetime


class StepSyncRequest(BaseModel):
    events: list[StepEventIn] = Field(min_length=1, max_length=500)


class StepEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_event_id: str
    steps_delta: int
    source: StepSource
    recorded_at: datetime


class ManualStepLogRequest(BaseModel):
    steps: int = Field(gt=0, le=100_000)
    recorded_at: datetime


class StepDeleteResponse(BaseModel):
    undo_action_id: uuid.UUID
    undo_expires_at: datetime


class TodayStatsResponse(BaseModel):
    date: date
    total_steps: int
    goal_steps: int
    steps_remaining: int
    progress_percent: float
    distance_km: float
    calories: int
    active_minutes: int
    goal_completed_at: datetime | None
    current_streak: int


class DailyStatRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    total_steps: int
    distance_km: float
    calories: int
    active_minutes: int
    goal_completed_at: datetime | None
