from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class GoalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    goal_steps: int
    baseline_steps: int
    is_manual_override: bool


class GoalUpdate(BaseModel):
    goal_steps: int = Field(gt=0, le=100_000)
