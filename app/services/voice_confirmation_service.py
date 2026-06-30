"""Confirm-before-acting ledger for voice-initiated destructive actions.

Mirrors undo_service.py's expiry pattern, but inverted: undo_service lets you
reverse something that already happened; this lets a voice command pause
*before* acting and wait for a spoken confirm/cancel within a short window.
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.voice import PendingVoiceConfirmation
from app.models.user import User
from app.services.voice_intent_service import Intent

CONFIRMATION_WINDOW_SECONDS = 15


async def create_pending(
    db: AsyncSession, user: User, intent: Intent, target_id: uuid.UUID | None = None
) -> PendingVoiceConfirmation:
    pending = PendingVoiceConfirmation(
        user_id=user.id,
        intent=intent.value,
        target_id=target_id,
        expires_at=datetime.now(timezone.utc) + timedelta(seconds=CONFIRMATION_WINDOW_SECONDS),
    )
    db.add(pending)
    await db.flush()
    return pending


def is_expired(pending: PendingVoiceConfirmation, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    return pending.consumed_at is not None or now > pending.expires_at


async def get_latest_pending(db: AsyncSession, user: User) -> PendingVoiceConfirmation | None:
    pending = await db.scalar(
        select(PendingVoiceConfirmation)
        .where(
            PendingVoiceConfirmation.user_id == user.id,
            PendingVoiceConfirmation.consumed_at.is_(None),
        )
        .order_by(PendingVoiceConfirmation.created_at.desc())
    )
    if pending is None or is_expired(pending):
        return None
    return pending


async def consume(db: AsyncSession, pending: PendingVoiceConfirmation) -> None:
    pending.consumed_at = datetime.now(timezone.utc)
    await db.flush()
