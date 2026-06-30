from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.steps import StepEvent
from app.models.undo import UndoAction
from app.models.user import User
from app.services import step_aggregation

UNDO_WINDOW_SECONDS = 5


class UndoError(Exception):
    pass


async def create_undo_action(
    db: AsyncSession,
    user: User,
    action_type: str,
    target_table: str,
    target_id: UUID,
    previous_state: dict,
) -> UndoAction:
    action = UndoAction(
        user_id=user.id,
        action_type=action_type,
        target_table=target_table,
        target_id=target_id,
        previous_state=previous_state,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=UNDO_WINDOW_SECONDS),
    )
    db.add(action)
    await db.flush()
    return action


def is_expired(action: UndoAction, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return action.consumed_at is not None or now > action.expires_at


async def apply_undo(db: AsyncSession, user: User, action: UndoAction) -> None:
    if action.user_id != user.id:
        raise UndoError("This action does not belong to the current user")
    if is_expired(action):
        raise UndoError("Undo window has expired")

    if action.target_table == "step_events":
        event = await db.get(StepEvent, action.target_id)
        if event is None or event.user_id != user.id:
            raise UndoError("Original step event no longer exists")
        event.deleted_at = None
        await db.flush()
        await step_aggregation.recompute_daily_stat(db, user, event.recorded_at.date())
    else:
        raise UndoError(f"Undo not supported for target_table={action.target_table!r}")

    action.consumed_at = datetime.now(timezone.utc)
    await db.flush()
