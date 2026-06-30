"""Raw StepEvent rows -> DailyStat aggregates, plus the downstream effects
(streak updates, milestone detection, activity feed posts) that should fire
whenever a day's totals change.
"""

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
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


def _apply_stat_fields(stat: DailyStat, total_steps: int, just_completed_goal: bool) -> None:
    stat.total_steps = total_steps
    stat.distance_km = round(total_steps * KM_PER_STEP, 2)
    stat.calories = round(total_steps * CALORIES_PER_STEP)
    stat.active_minutes = total_steps // STEPS_PER_ACTIVE_MINUTE
    if just_completed_goal:
        stat.goal_completed_at = datetime.now(timezone.utc)


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
        _apply_stat_fields(stat, total_steps, just_completed_goal)
        try:
            # SAVEPOINT, not a full-session rollback - see the matching
            # comment in get_or_create_daily_goal for why a plain
            # db.rollback() here would crash later attribute access on
            # `user`/`goal` (already loaded earlier in this same session)
            # with MissingGreenlet instead of just losing this one insert.
            async with db.begin_nested():
                db.add(stat)
                await db.flush()
        except IntegrityError:
            # Lost a race against a concurrent recompute for the same
            # user+date creating the DailyStat row first (identical TOCTOU
            # pattern to get_or_create_daily_goal). Re-fetch the winner's
            # row and re-apply these field values to it instead of erroring.
            stat = await db.scalar(
                select(DailyStat).where(
                    DailyStat.user_id == user.id, DailyStat.date == target_date
                )
            )
            if stat is None:
                raise
            just_completed_goal = total_steps >= goal.goal_steps and stat.goal_completed_at is None
            _apply_stat_fields(stat, total_steps, just_completed_goal)
            await db.flush()
    else:
        _apply_stat_fields(stat, total_steps, just_completed_goal)
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


async def soft_delete_step_event(db: AsyncSession, user: User, event: StepEvent) -> None:
    """Soft-deletes a step event and recomputes that day's aggregate.

    Does NOT create an undo record - shared by the REST DELETE endpoint and
    the voice-command delete flow, both of which create their own
    app.services.undo_service record afterward. Kept separate to avoid a
    step_aggregation <-> undo_service import cycle (undo_service already
    calls back into step_aggregation.recompute_daily_stat to restore state).
    """
    event.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await recompute_daily_stat(db, user, event.recorded_at.date())
