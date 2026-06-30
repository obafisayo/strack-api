from datetime import date, timedelta

from app.services.streak_service import next_streak_state

TODAY = date(2026, 6, 30)
YESTERDAY = TODAY - timedelta(days=1)


def test_goal_not_completed_leaves_streak_unchanged():
    assert next_streak_state(5, YESTERDAY, TODAY, goal_completed=False) == (5, YESTERDAY)


def test_first_ever_completion_starts_streak_at_one():
    assert next_streak_state(0, None, TODAY, goal_completed=True) == (1, TODAY)


def test_consecutive_day_increments_streak():
    assert next_streak_state(5, YESTERDAY, TODAY, goal_completed=True) == (6, TODAY)


def test_gap_day_resets_streak_to_one():
    last_active = TODAY - timedelta(days=3)
    assert next_streak_state(5, last_active, TODAY, goal_completed=True) == (1, TODAY)


def test_same_day_recompute_is_idempotent():
    assert next_streak_state(6, TODAY, TODAY, goal_completed=True) == (6, TODAY)


def test_backfilled_past_day_does_not_disturb_active_streak():
    older_date = TODAY - timedelta(days=5)
    assert next_streak_state(6, TODAY, older_date, goal_completed=True) == (6, TODAY)
