from datetime import date, timedelta

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.goals import DailyGoal
from app.schemas.goals import GoalRead, GoalUpdate
from app.services.daily_goal_service import get_or_create_daily_goal

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("/today", response_model=GoalRead)
async def get_today_goal(user: CurrentUser, db: DbSession) -> GoalRead:
    goal = await get_or_create_daily_goal(db, user, date.today())
    await db.commit()
    return GoalRead.model_validate(goal)


@router.patch("/today", response_model=GoalRead)
async def update_today_goal(payload: GoalUpdate, user: CurrentUser, db: DbSession) -> GoalRead:
    goal = await get_or_create_daily_goal(db, user, date.today())
    goal.goal_steps = payload.goal_steps
    goal.is_manual_override = True
    await db.commit()
    await db.refresh(goal)
    return GoalRead.model_validate(goal)


@router.get("/history", response_model=list[GoalRead])
async def get_goal_history(
    user: CurrentUser, db: DbSession, days: int = Query(default=14, ge=1, le=90)
) -> list[GoalRead]:
    start_date = date.today() - timedelta(days=days - 1)
    rows = await db.scalars(
        select(DailyGoal)
        .where(DailyGoal.user_id == user.id, DailyGoal.date >= start_date)
        .order_by(DailyGoal.date.desc())
    )
    return [GoalRead.model_validate(row) for row in rows.all()]
