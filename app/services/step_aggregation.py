"""Raw StepEvent rows -> DailyStat aggregates, plus the downstream effects
(streak updates, milestone detection, activity feed posts) that should fire
whenever a day's totals change.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.steps import DailyStat, StepEvent, StepSource
from app.models.user import User
from app.schemas.steps import StepEventIn
from app.services import feed_service, milestone_service, streak_service
from app.services.daily_goal_service import get_or_create_daily_goal

# Rough, tunable conversion constants - not medically/biometrically precise,
# good enough for the "Real-World Data Formatter" feature (human-readable
# distance/calories from a raw step count).
KM_PER_STEP = 0.0008
CALORIES_PER_STEP = 0.04
STEPS_PER_ACTIVE_MINUTE = 100


async def record_step_events(
    db: AsyncSession, user: User, events: list[StepEventIn], source: StepSource
) -> set[date]:
    if not events:
        return set()

    rows = [
        {
            "id": uuid.uuid4(),
            "user_id": user.id,
            "client_event_id": event.client_event_id,
            "steps_delta": event.steps_delta,
            "source": source,
            "recorded_at": event.recorded_at,
        }
        for event in events
    ]
    stmt = (
        pg_insert(StepEvent)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["user_id", "client_event_id"])
    )
    await db.execute(stmt)

    affected_dates = {event.recorded_at.date() for event in events}
    for target_date in affected_dates:
        await recompute_daily_stat(db, user, target_date)

    await db.commit()
    return affected_dates


async def recompute_daily_stat(db: AsyncSession, user: User, target_date: date) -> DailyStat:
    total_steps = await db.scalar(
        select(func.coalesce(func.sum(StepEvent.steps_delta), 0)).where(
            StepEvent.user_id == user.id,
            StepEvent.deleted_at.is_(None),
            func.date(StepEvent.recorded_at) == target_date,
        )
    )

    goal = await get_or_create_daily_goal(db, user, target_date)

    stat = await db.scalar(
        select(DailyStat).where(DailyStat.user_id == user.id, DailyStat.date == target_date)
    )
    was_already_completed = stat is not None and stat.goal_completed_at is not None
    just_completed_goal = total_steps >= goal.goal_steps and not was_already_completed

    if stat is None:
        stat = DailyStat(user_id=user.id, date=target_date)
        db.add(stat)

    stat.total_steps = total_steps
    stat.distance_km = round(total_steps * KM_PER_STEP, 2)
    stat.calories = round(total_steps * CALORIES_PER_STEP)
    stat.active_minutes = total_steps // STEPS_PER_ACTIVE_MINUTE
    if just_completed_goal:
        stat.goal_completed_at = datetime.now(timezone.utc)
    await db.flush()

    await streak_service.update_streak(
        db, user, target_date, goal_completed=stat.goal_completed_at is not None
    )
    await milestone_service.check_and_record_milestones(db, user, stat, just_completed_goal)

    if just_completed_goal:
        await feed_service.create_activity_summary_post(db, user, stat)

    return stat


async def get_daily_stat(db: AsyncSession, user: User, target_date: date) -> DailyStat | None:
    return await db.scalar(
        select(DailyStat).where(DailyStat.user_id == user.id, DailyStat.date == target_date)
    )
