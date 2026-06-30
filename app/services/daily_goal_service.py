from datetime import date

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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
    try:
        # SAVEPOINT, not a full-session rollback: a plain db.rollback() on
        # conflict expires every object already loaded in this session
        # (e.g. `user`, fetched earlier in the same request) - any attribute
        # access on them afterward tries an implicit sync reload that
        # crashes with MissingGreenlet outside the async bridge. begin_nested
        # contains the rollback to just this insert.
        async with db.begin_nested():
            db.add(goal)
            await db.flush()
    except IntegrityError:
        # Lost a race against a concurrent request creating this same day's
        # goal (TOCTOU between the SELECT above and this INSERT, both seeing
        # "no goal yet" before either commits - reproduced live by
        # test_listen_concurrent_listen_requests_for_same_user). The other
        # request won; just fetch what it created instead of erroring.
        goal = await db.scalar(
            select(DailyGoal).where(DailyGoal.user_id == user.id, DailyGoal.date == target_date)
        )
        if goal is None:
            raise
    return goal
