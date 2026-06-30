from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.goals import DailyGoal
from app.models.user import ActivityLevel, AgeGroup, User
from app.services.goal_service import compute_baseline_goal


async def get_or_create_daily_goal(db: AsyncSession, user: User, target_date: date) -> DailyGoal:
    goal = await db.scalar(
        select(DailyGoal).where(DailyGoal.user_id == user.id, DailyGoal.date == target_date)
    )
    if goal is not None:
        return goal

    baseline = compute_baseline_goal(
        user.age_group or AgeGroup.AGE_18_40,
        user.activity_level or ActivityLevel.LIGHTLY_ACTIVE,
    )
    goal = DailyGoal(
        user_id=user.id,
        date=target_date,
        goal_steps=baseline,
        baseline_steps=baseline,
        is_manual_override=False,
    )
    db.add(goal)
    await db.flush()
    return goal
