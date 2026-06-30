"""Dispatches a matched voice Intent to the corresponding action and builds
the spoken reply text. Read-intents reuse the same service-layer functions
the REST endpoints already call (step_aggregation, streak_service,
leaderboard_service) - nothing here re-implements that logic.
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.steps import StepEvent
from app.models.user import User
from app.schemas.leaderboard import LeaderboardScope
from app.services import feed_service, step_aggregation, streak_service, undo_service
from app.services import voice_confirmation_service
from app.services.daily_goal_service import get_or_create_daily_goal
from app.services.leaderboard_service import get_leaderboard
from app.services.voice_intent_service import Intent

ActionResult = tuple[str, dict | None]


async def execute(db: AsyncSession, user: User, intent: Intent) -> ActionResult:
    if intent == Intent.QUERY_STEPS:
        return await _query_steps(db, user)
    if intent == Intent.QUERY_STREAK:
        return await _query_streak(db, user)
    if intent == Intent.QUERY_LEADERBOARD:
        return await _query_leaderboard(db, user)
    if intent == Intent.SHARE_PROGRESS:
        return await _share_progress(db, user)
    if intent == Intent.DELETE_LAST_ENTRY:
        return await _request_delete_last_entry(db, user)
    if intent == Intent.CONFIRM:
        return await _handle_confirm(db, user)
    if intent == Intent.CANCEL:
        return await _handle_cancel(db, user)
    return "Sorry, I didn't understand that. Please try again.", None


async def _query_steps(db: AsyncSession, user: User) -> ActionResult:
    today = date.today()
    stat = await step_aggregation.get_daily_stat(db, user, today)
    goal = await get_or_create_daily_goal(db, user, today)
    await db.commit()

    steps = stat.total_steps if stat else 0
    remaining = max(goal.goal_steps - steps, 0)
    text = f"You've completed {steps} steps today."
    text += (
        f" You have {remaining} steps remaining to reach today's goal."
        if remaining > 0
        else " You've already reached today's goal!"
    )
    return text, {"steps": steps, "goal_steps": goal.goal_steps, "steps_remaining": remaining}


async def _query_streak(db: AsyncSession, user: User) -> ActionResult:
    streak = await streak_service.get_or_create_streak(db, user)
    await db.commit()

    days = streak.current_streak
    text = (
        f"You're on a {days}-day streak. Keep it up!"
        if days > 0
        else "You don't have an active streak yet - complete today's goal to start one."
    )
    return text, {"current_streak": days, "longest_streak": streak.longest_streak}


async def _query_leaderboard(db: AsyncSession, user: User) -> ActionResult:
    entries, my_rank = await get_leaderboard(db, user, LeaderboardScope.TODAY)
    text = (
        f"You're ranked number {my_rank} on today's leaderboard."
        if my_rank is not None
        else "You're not on today's leaderboard yet."
    )
    return text, {"rank": my_rank, "entry_count": len(entries)}


async def _share_progress(db: AsyncSession, user: User) -> ActionResult:
    post = await feed_service.create_community_share_post(db, user, message=None)
    await db.commit()
    return "Your progress has been shared to the community feed.", {"post_id": str(post.id)}


async def _request_delete_last_entry(db: AsyncSession, user: User) -> ActionResult:
    event = await db.scalar(
        select(StepEvent)
        .where(StepEvent.user_id == user.id, StepEvent.deleted_at.is_(None))
        .order_by(StepEvent.recorded_at.desc())
    )
    if event is None:
        return "You don't have any step entries to delete.", None

    pending = await voice_confirmation_service.create_pending(
        db, user, Intent.DELETE_LAST_ENTRY, target_id=event.id
    )
    await db.commit()

    text = (
        f"Are you sure you want to delete your last entry of {event.steps_delta} steps? "
        "Say yes to confirm, or no to cancel."
    )
    return text, {"pending_confirmation_id": str(pending.id), "steps_delta": event.steps_delta}


async def _handle_confirm(db: AsyncSession, user: User) -> ActionResult:
    pending = await voice_confirmation_service.get_latest_pending(db, user)
    if pending is None:
        return "There's nothing waiting for confirmation.", None

    if pending.intent != Intent.DELETE_LAST_ENTRY.value:
        await voice_confirmation_service.consume(db, pending)
        await db.commit()
        return "Sorry, I couldn't process that confirmation.", None

    event = await db.get(StepEvent, pending.target_id)
    if event is None or event.deleted_at is not None:
        await voice_confirmation_service.consume(db, pending)
        await db.commit()
        return "That entry no longer exists.", None

    await step_aggregation.soft_delete_step_event(db, user, event)
    action = await undo_service.create_undo_action(
        db,
        user,
        action_type="delete_step_event",
        target_table="step_events",
        target_id=event.id,
        previous_state={"deleted_at": None},
    )
    await voice_confirmation_service.consume(db, pending)
    await db.commit()

    return (
        f"Deleted your last entry of {event.steps_delta} steps.",
        {"deleted_steps": event.steps_delta, "undo_action_id": str(action.id)},
    )


async def _handle_cancel(db: AsyncSession, user: User) -> ActionResult:
    pending = await voice_confirmation_service.get_latest_pending(db, user)
    if pending is None:
        return "There's nothing to cancel.", None

    await voice_confirmation_service.consume(db, pending)
    await db.commit()
    return "Okay, cancelled.", None
