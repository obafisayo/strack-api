import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    achieved_at: datetime
    extra_data: dict
