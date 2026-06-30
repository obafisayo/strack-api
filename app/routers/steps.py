import uuid
from datetime import date, datetime, timedelta, timezone
from enum import Enum

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.steps import DailyStat, StepEvent, StepSource
from app.schemas.steps import (
    DailyStatRead,
    ManualStepLogRequest,
    StepDeleteResponse,
    StepEventIn,
    StepSyncRequest,
    TodayStatsResponse,
)
from app.services import step_aggregation, streak_service, undo_service
from app.services.daily_goal_service import get_or_create_daily_goal

router = APIRouter(prefix="/steps", tags=["steps"])


class HistoryRange(str, Enum):
    WEEK = "week"
    MONTH = "month"


@router.post("/sync", response_model=TodayStatsResponse)
async def sync_steps(payload: StepSyncRequest, user: CurrentUser, db: DbSession) -> TodayStatsResponse:
    await step_aggregation.record_step_events(db, user, payload.events, source=StepSource.SENSOR)
    return await _today_stats(db, user)


@router.post("/manual", response_model=TodayStatsResponse, status_code=status.HTTP_201_CREATED)
async def log_manual_steps(
    payload: ManualStepLogRequest, user: CurrentUser, db: DbSession
) -> TodayStatsResponse:
    event = StepEventIn(
        client_event_id=f"manual-{uuid.uuid4()}",
        steps_delta=payload.steps,
        recorded_at=payload.recorded_at,
    )
    await step_aggregation.record_step_events(db, user, [event], source=StepSource.MANUAL)
    return await _today_stats(db, user)


@router.delete("/{event_id}", response_model=StepDeleteResponse)
async def delete_step_event(
    event_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> StepDeleteResponse:
    event = await db.get(StepEvent, event_id)
    if event is None or event.user_id != user.id or event.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Step entry not found")

    event.deleted_at = datetime.now(timezone.utc)
    await db.flush()

    action = await undo_service.create_undo_action(
        db,
        user,
        action_type="delete_step_event",
        target_table="step_events",
        target_id=event.id,
        previous_state={"deleted_at": None},
    )
    await step_aggregation.recompute_daily_stat(db, user, event.recorded_at.date())
    await db.commit()

    return StepDeleteResponse(undo_action_id=action.id, undo_expires_at=action.expires_at)


@router.get("/today", response_model=TodayStatsResponse)
async def get_today(user: CurrentUser, db: DbSession) -> TodayStatsResponse:
    return await _today_stats(db, user)


@router.get("/history", response_model=list[DailyStatRead])
async def get_history(
    user: CurrentUser, db: DbSession, range: HistoryRange = Query(default=HistoryRange.WEEK)
) -> list[DailyStatRead]:
    days = 7 if range == HistoryRange.WEEK else 30
    start_date = date.today() - timedelta(days=days - 1)
    rows = await db.scalars(
        select(DailyStat)
        .where(DailyStat.user_id == user.id, DailyStat.date >= start_date)
        .order_by(DailyStat.date.asc())
    )
    return [DailyStatRead.model_validate(row) for row in rows.all()]


@router.get("/daily/{stat_date}", response_model=DailyStatRead)
async def get_daily(stat_date: date, user: CurrentUser, db: DbSession) -> DailyStatRead:
    stat = await step_aggregation.get_daily_stat(db, user, stat_date)
    if stat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No activity recorded for this date")
    return DailyStatRead.model_validate(stat)


async def _today_stats(db: DbSession, user) -> TodayStatsResponse:
    today = date.today()
    stat = await step_aggregation.get_daily_stat(db, user, today)
    goal = await get_or_create_daily_goal(db, user, today)
    streak = await streak_service.get_or_create_streak(db, user)
    await db.commit()

    total_steps = stat.total_steps if stat else 0
    return TodayStatsResponse(
        date=today,
        total_steps=total_steps,
        goal_steps=goal.goal_steps,
        steps_remaining=max(goal.goal_steps - total_steps, 0),
        progress_percent=round(min(total_steps / goal.goal_steps, 1.0) * 100, 1)
        if goal.goal_steps
        else 0.0,
        distance_km=stat.distance_km if stat else 0.0,
        calories=stat.calories if stat else 0,
        active_minutes=stat.active_minutes if stat else 0,
        goal_completed_at=stat.goal_completed_at if stat else None,
        current_streak=streak.current_streak,
    )
