from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.streaks import Streak
from app.models.user import User


def next_streak_state(
    current_streak: int,
    last_active_date: date | None,
    target_date: date,
    goal_completed: bool,
) -> tuple[int, date | None]:
    """Pure decision logic for how a streak evolves when a given day's goal
    completion status is known. Kept side-effect free so it's unit-testable
    without a database.
    """
    if not goal_completed:
        return current_streak, last_active_date

    if last_active_date == target_date:
        return current_streak, last_active_date  # already counted

    if last_active_date == target_date - timedelta(days=1):
        return current_streak + 1, target_date

    if last_active_date is None or last_active_date < target_date - timedelta(days=1):
        return 1, target_date

    # target_date is older than last_active_date (a backfilled/manual past
    # entry) - leave the active streak chain untouched.
    return current_streak, last_active_date


async def get_or_create_streak(db: AsyncSession, user: User) -> Streak:
    streak = await db.scalar(select(Streak).where(Streak.user_id == user.id))
    if streak is None:
        streak = Streak(user_id=user.id, current_streak=0, longest_streak=0, last_active_date=None)
        db.add(streak)
        await db.flush()
    return streak


async def update_streak(
    db: AsyncSession, user: User, target_date: date, goal_completed: bool
) -> Streak:
    streak = await get_or_create_streak(db, user)
    new_current, new_last_active = next_streak_state(
        streak.current_streak, streak.last_active_date, target_date, goal_completed
    )
    streak.current_streak = new_current
    streak.last_active_date = new_last_active
    streak.longest_streak = max(streak.longest_streak, new_current)
    await db.flush()
    return streak
