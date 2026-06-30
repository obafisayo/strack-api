"""Dispatches a matched voice Intent to the corresponding action and builds
the spoken reply text. Read-intents reuse the same service-layer functions
the REST endpoints already call (step_aggregation, streak_service,
leaderboard_service) - nothing here re-implements that logic.

Reply text is always built via voice_localization.t(language, ...) - never
an inline English string - so the language a voice was picked for (see
yarngpt_client.VOICE_BY_LANGUAGE) actually matches the words it's asked to
speak.
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
from app.services.voice_localization import t

ActionResult = tuple[str, dict | None]


async def execute(db: AsyncSession, user: User, intent: Intent, language: str) -> ActionResult:
    if intent == Intent.QUERY_STEPS:
        return await _query_steps(db, user, language)
    if intent == Intent.QUERY_STREAK:
        return await _query_streak(db, user, language)
    if intent == Intent.QUERY_LEADERBOARD:
        return await _query_leaderboard(db, user, language)
    if intent == Intent.SHARE_PROGRESS:
        return await _share_progress(db, user, language)
    if intent == Intent.DELETE_LAST_ENTRY:
        return await _request_delete_last_entry(db, user, language)
    if intent == Intent.CONFIRM:
        return await _handle_confirm(db, user, language)
    if intent == Intent.CANCEL:
        return await _handle_cancel(db, user, language)
    return t(language, "unknown_intent"), None


async def _query_steps(db: AsyncSession, user: User, language: str) -> ActionResult:
    today = date.today()
    stat = await step_aggregation.get_daily_stat(db, user, today)
    goal = await get_or_create_daily_goal(db, user, today)
    await db.commit()

    steps = stat.total_steps if stat else 0
    remaining = max(goal.goal_steps - steps, 0)
    text = (
        t(language, "steps_remaining", steps=steps, remaining=remaining)
        if remaining > 0
        else t(language, "steps_goal_reached", steps=steps)
    )
    return text, {"steps": steps, "goal_steps": goal.goal_steps, "steps_remaining": remaining}


async def _query_streak(db: AsyncSession, user: User, language: str) -> ActionResult:
    streak = await streak_service.get_or_create_streak(db, user)
    await db.commit()

    days = streak.current_streak
    text = (
        t(language, "streak_active", days=days) if days > 0 else t(language, "streak_none")
    )
    return text, {"current_streak": days, "longest_streak": streak.longest_streak}


async def _query_leaderboard(db: AsyncSession, user: User, language: str) -> ActionResult:
    entries, my_rank = await get_leaderboard(db, user, LeaderboardScope.TODAY)
    text = (
        t(language, "leaderboard_ranked", rank=my_rank)
        if my_rank is not None
        else t(language, "leaderboard_unranked")
    )
    return text, {"rank": my_rank, "entry_count": len(entries)}


async def _share_progress(db: AsyncSession, user: User, language: str) -> ActionResult:
    post = await feed_service.create_community_share_post(db, user, message=None)
    await db.commit()
    return t(language, "progress_shared"), {"post_id": str(post.id)}


async def _request_delete_last_entry(db: AsyncSession, user: User, language: str) -> ActionResult:
    event = await db.scalar(
        select(StepEvent)
        .where(StepEvent.user_id == user.id, StepEvent.deleted_at.is_(None))
        .order_by(StepEvent.recorded_at.desc())
    )
    if event is None:
        return t(language, "no_entries_to_delete"), None

    pending = await voice_confirmation_service.create_pending(
        db, user, Intent.DELETE_LAST_ENTRY, target_id=event.id
    )
    await db.commit()

    text = t(language, "delete_confirm_prompt", steps=event.steps_delta)
    return text, {"pending_confirmation_id": str(pending.id), "steps_delta": event.steps_delta}


async def _handle_confirm(db: AsyncSession, user: User, language: str) -> ActionResult:
    pending = await voice_confirmation_service.get_latest_pending(db, user)
    if pending is None:
        return t(language, "nothing_pending"), None

    if pending.intent != Intent.DELETE_LAST_ENTRY.value:
        await voice_confirmation_service.consume(db, pending)
        await db.commit()
        return t(language, "confirm_failed"), None

    event = await db.get(StepEvent, pending.target_id)
    if event is None or event.deleted_at is not None:
        await voice_confirmation_service.consume(db, pending)
        await db.commit()
        return t(language, "entry_gone"), None

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
        t(language, "delete_confirmed", steps=event.steps_delta),
        {"deleted_steps": event.steps_delta, "undo_action_id": str(action.id)},
    )


async def _handle_cancel(db: AsyncSession, user: User, language: str) -> ActionResult:
    pending = await voice_confirmation_service.get_latest_pending(db, user)
    if pending is None:
        return t(language, "nothing_to_cancel"), None

    await voice_confirmation_service.consume(db, pending)
    await db.commit()
    return t(language, "cancelled"), None
