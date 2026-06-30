import uuid
from datetime import datetime, timedelta, timezone

from app.models.voice import PendingVoiceConfirmation
from app.services.voice_confirmation_service import is_expired


def _make_pending(expires_in_seconds: float, consumed: bool = False) -> PendingVoiceConfirmation:
    now = datetime.now(timezone.utc)
    return PendingVoiceConfirmation(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        intent="delete_last_entry",
        target_id=uuid.uuid4(),
        expires_at=now + timedelta(seconds=expires_in_seconds),
        consumed_at=now if consumed else None,
    )


def test_pending_within_window_is_not_expired():
    assert is_expired(_make_pending(expires_in_seconds=10)) is False


def test_pending_past_window_is_expired():
    assert is_expired(_make_pending(expires_in_seconds=-1)) is True


def test_consumed_pending_is_always_expired():
    assert is_expired(_make_pending(expires_in_seconds=10, consumed=True)) is True
