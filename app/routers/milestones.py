from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.milestones import Milestone
from app.schemas.milestones import MilestoneRead

router = APIRouter(prefix="/milestones", tags=["milestones"])


@router.get("", response_model=list[MilestoneRead])
async def list_milestones(user: CurrentUser, db: DbSession) -> list[MilestoneRead]:
    rows = await db.scalars(
        select(Milestone)
        .where(Milestone.user_id == user.id)
        .order_by(Milestone.achieved_at.desc())
    )
    return [MilestoneRead.model_validate(row) for row in rows.all()]
