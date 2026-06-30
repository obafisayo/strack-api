from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.deps import CurrentUser, DbSession
from app.models.steps import StepEvent
from app.schemas.sync import SyncStatusResponse

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status(user: CurrentUser, db: DbSession) -> SyncStatusResponse:
    last_synced_at = await db.scalar(
        select(func.max(StepEvent.created_at)).where(StepEvent.user_id == user.id)
    )
    return SyncStatusResponse(last_synced_at=last_synced_at)
