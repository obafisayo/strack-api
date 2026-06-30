from datetime import datetime

from pydantic import BaseModel


class SyncStatusResponse(BaseModel):
    last_synced_at: datetime | None
