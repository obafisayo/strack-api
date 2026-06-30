import uuid
from datetime import datetime, timedelta, timezone

from app.models.undo import UndoAction
from app.services.undo_service import is_expired


def _make_action(expires_in_seconds: float, consumed: bool = False) -> UndoAction:
    now = datetime.now(timezone.utc)
    return UndoAction(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        action_type="delete_step_event",
        target_table="step_events",
        target_id=uuid.uuid4(),
        previous_state={},
        expires_at=now + timedelta(seconds=expires_in_seconds),
        consumed_at=now if consumed else None,
    )


def test_action_within_window_is_not_expired():
    action = _make_action(expires_in_seconds=5)
    assert is_expired(action) is False


def test_action_past_window_is_expired():
    action = _make_action(expires_in_seconds=-1)
    assert is_expired(action) is True


def test_consumed_action_is_always_expired():
    action = _make_action(expires_in_seconds=5, consumed=True)
    assert is_expired(action) is True
