"""Adversarial endpoint tests for /steps/* - sync, manual, delete, today,
history, daily.

The single most important guarantee under test here is idempotency:
record_step_events() relies on a Postgres ON CONFLICT DO NOTHING upsert
keyed on (user_id, client_event_id) - these tests exist specifically because
that's the kind of thing that's easy to silently break in a refactor and
SQLite couldn't have caught (it doesn't speak this dialect's upsert syntax),
which is exactly why this test file needs a real Postgres test database.
"""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def iso_at(offset: timedelta) -> str:
    return (datetime.now(timezone.utc) + offset).isoformat()


# --------------------------------------------------------------------------
# Auth guard - every steps endpoint requires a valid bearer token
# --------------------------------------------------------------------------

STEPS_ENDPOINTS_REQUIRING_AUTH = [
    pytest.param("POST", "/api/v1/steps/sync", {"events": []}, id="sync"),
    pytest.param("POST", "/api/v1/steps/manual", {"steps": 100, "recorded_at": iso_now()}, id="manual"),
    pytest.param("DELETE", f"/api/v1/steps/{uuid.uuid4()}", None, id="delete"),
    pytest.param("GET", "/api/v1/steps/today", None, id="today"),
    pytest.param("GET", "/api/v1/steps/history", None, id="history"),
    pytest.param("GET", "/api/v1/steps/daily/2026-01-01", None, id="daily"),
]


@pytest.mark.parametrize("method,path,json_body", STEPS_ENDPOINTS_REQUIRING_AUTH)
async def test_steps_endpoints_reject_unauthenticated_requests(client, method, path, json_body):
    response = await client.request(method, path, json=json_body)
    assert response.status_code == 401


@pytest.mark.parametrize("method,path,json_body", STEPS_ENDPOINTS_REQUIRING_AUTH)
async def test_steps_endpoints_reject_garbage_bearer_token(client, method, path, json_body):
    response = await client.request(
        method, path, json=json_body, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert response.status_code == 401


# --------------------------------------------------------------------------
# /steps/sync - idempotency is the core contract under test
# --------------------------------------------------------------------------

async def test_sync_identical_client_event_id_replayed_does_not_double_count(client, auth_user):
    event = {"client_event_id": "replay-1", "steps_delta": 1000, "recorded_at": iso_now()}
    headers = auth_user["headers"]

    first = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=headers)
    second = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=headers)
    third = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 200
    assert first.json()["total_steps"] == 1000
    assert second.json()["total_steps"] == 1000
    assert third.json()["total_steps"] == 1000


async def test_sync_duplicate_client_event_id_within_same_batch_counts_once(client, auth_user):
    event = {"client_event_id": "same-batch-dup", "steps_delta": 500, "recorded_at": iso_now()}
    response = await client.post(
        "/api/v1/steps/sync", json={"events": [event, event, event]}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    assert response.json()["total_steps"] == 500


async def test_sync_different_event_ids_same_steps_value_all_count(client, auth_user):
    now = iso_now()
    events = [{"client_event_id": f"distinct-{i}", "steps_delta": 100, "recorded_at": now} for i in range(5)]
    response = await client.post("/api/v1/steps/sync", json={"events": events}, headers=auth_user["headers"])
    assert response.status_code == 200
    assert response.json()["total_steps"] == 500


async def test_sync_concurrent_identical_requests_remain_idempotent(client, auth_user):
    event = {"client_event_id": "concurrent-replay", "steps_delta": 250, "recorded_at": iso_now()}
    headers = auth_user["headers"]

    responses = await asyncio.gather(
        *[client.post("/api/v1/steps/sync", json={"events": [event]}, headers=headers) for _ in range(5)]
    )
    assert all(r.status_code == 200 for r in responses)

    final = await client.get("/api/v1/steps/today", headers=headers)
    assert final.json()["total_steps"] == 250


async def test_sync_max_batch_size_500_is_accepted(client, auth_user):
    now = iso_now()
    events = [{"client_event_id": f"batch500-{i}", "steps_delta": 1, "recorded_at": now} for i in range(500)]
    response = await client.post("/api/v1/steps/sync", json={"events": events}, headers=auth_user["headers"])
    assert response.status_code == 200
    assert response.json()["total_steps"] == 500


async def test_sync_batch_of_501_is_rejected(client, auth_user):
    now = iso_now()
    events = [{"client_event_id": f"batch501-{i}", "steps_delta": 1, "recorded_at": now} for i in range(501)]
    response = await client.post("/api/v1/steps/sync", json={"events": events}, headers=auth_user["headers"])
    assert response.status_code == 422


async def test_sync_empty_events_array_is_rejected(client, auth_user):
    response = await client.post("/api/v1/steps/sync", json={"events": []}, headers=auth_user["headers"])
    assert response.status_code == 422


INVALID_SYNC_EVENT_FIELDS = [
    pytest.param({"client_event_id": "x", "steps_delta": 0, "recorded_at": iso_now()}, id="steps-delta-zero"),
    pytest.param({"client_event_id": "x", "steps_delta": -1, "recorded_at": iso_now()}, id="steps-delta-negative"),
    pytest.param({"client_event_id": "x", "steps_delta": 100_001, "recorded_at": iso_now()}, id="steps-delta-over-max"),
    pytest.param({"client_event_id": "x", "steps_delta": "a lot", "recorded_at": iso_now()}, id="steps-delta-wrong-type-string"),
    pytest.param({"client_event_id": "x", "steps_delta": 1.5, "recorded_at": iso_now()}, id="steps-delta-float-fractional"),
    pytest.param({"client_event_id": "x" * 101, "steps_delta": 1, "recorded_at": iso_now()}, id="client-event-id-101-chars-over-max"),
    pytest.param({"client_event_id": "", "steps_delta": 1, "recorded_at": iso_now()}, id="client-event-id-empty-string"),
    pytest.param({"client_event_id": "x", "steps_delta": 1, "recorded_at": "not-a-date"}, id="recorded-at-garbage-string"),
    pytest.param({"client_event_id": "x", "steps_delta": 1, "recorded_at": "2026-13-45T99:99:99"}, id="recorded-at-invalid-calendar-values"),
    pytest.param({"client_event_id": "x", "steps_delta": 1}, id="missing-recorded-at"),
    pytest.param({"steps_delta": 1, "recorded_at": iso_now()}, id="missing-client-event-id"),
    pytest.param({"client_event_id": "x", "recorded_at": iso_now()}, id="missing-steps-delta"),
]


@pytest.mark.parametrize("bad_event", INVALID_SYNC_EVENT_FIELDS)
async def test_sync_rejects_invalid_event_fields(client, auth_user, bad_event):
    response = await client.post(
        "/api/v1/steps/sync", json={"events": [bad_event]}, headers=auth_user["headers"]
    )
    assert response.status_code == 422


async def test_sync_steps_delta_exactly_at_max_boundary_accepted(client, auth_user):
    event = {"client_event_id": "max-boundary", "steps_delta": 100_000, "recorded_at": iso_now()}
    response = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=auth_user["headers"])
    assert response.status_code == 200
    assert response.json()["total_steps"] == 100_000


async def test_sync_steps_delta_exactly_one_accepted(client, auth_user):
    event = {"client_event_id": "min-boundary", "steps_delta": 1, "recorded_at": iso_now()}
    response = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=auth_user["headers"])
    assert response.status_code == 200
    assert response.json()["total_steps"] == 1


async def test_sync_client_event_id_exactly_100_chars_accepted(client, auth_user):
    event = {"client_event_id": "x" * 100, "steps_delta": 1, "recorded_at": iso_now()}
    response = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=auth_user["headers"])
    assert response.status_code == 200


TIMEZONE_VARIANTS = [
    pytest.param("+00:00", id="utc-offset"),
    pytest.param("+14:00", id="furthest-ahead-offset-kiribati"),
    pytest.param("-12:00", id="furthest-behind-offset-baker-island"),
    pytest.param("Z", id="zulu-suffix"),
]


@pytest.mark.parametrize("suffix", TIMEZONE_VARIANTS)
async def test_sync_accepts_various_timezone_offsets(client, auth_user, suffix):
    naive = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    event = {"client_event_id": f"tz-{suffix}", "steps_delta": 10, "recorded_at": naive + suffix}
    response = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=auth_user["headers"])
    assert response.status_code == 200


async def test_sync_event_recorded_far_in_the_future_still_accepted(client, auth_user):
    event = {
        "client_event_id": "future-event",
        "steps_delta": 50,
        "recorded_at": iso_at(timedelta(days=3650)),
    }
    response = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=auth_user["headers"])
    # No application-level validation currently rejects future dates -
    # documents that this succeeds rather than assuming it's blocked.
    assert response.status_code == 200


async def test_sync_event_recorded_far_in_the_past_still_accepted(client, auth_user):
    event = {
        "client_event_id": "ancient-event",
        "steps_delta": 50,
        "recorded_at": iso_at(timedelta(days=-3650)),
    }
    response = await client.post("/api/v1/steps/sync", json={"events": [event]}, headers=auth_user["headers"])
    assert response.status_code == 200


async def test_sync_two_users_same_client_event_id_do_not_collide(client, register_user):
    user_a = (await register_user()).json()
    user_b = (await register_user()).json()
    event = {"client_event_id": "shared-id-across-users", "steps_delta": 300, "recorded_at": iso_now()}

    resp_a = await client.post(
        "/api/v1/steps/sync",
        json={"events": [event]},
        headers={"Authorization": f"Bearer {user_a['access_token']}"},
    )
    resp_b = await client.post(
        "/api/v1/steps/sync",
        json={"events": [event]},
        headers={"Authorization": f"Bearer {user_b['access_token']}"},
    )
    assert resp_a.status_code == 200
    assert resp_b.status_code == 200
    assert resp_a.json()["total_steps"] == 300
    assert resp_b.json()["total_steps"] == 300


async def test_sync_non_json_content_type_rejected(client, auth_user):
    response = await client.post(
        "/api/v1/steps/sync",
        content=b"events=not-json",
        headers={**auth_user["headers"], "Content-Type": "text/plain"},
    )
    assert response.status_code in (400, 415, 422)


async def test_sync_malformed_json_body_rejected(client, auth_user):
    response = await client.post(
        "/api/v1/steps/sync",
        content=b'{"events": [{"client_event_id": "x", "steps_delta": 1, "recorded_at":}]}',
        headers={**auth_user["headers"], "Content-Type": "application/json"},
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# /steps/manual
# --------------------------------------------------------------------------

async def test_manual_log_creates_entry_and_updates_today(client, auth_user):
    response = await client.post(
        "/api/v1/steps/manual",
        json={"steps": 2500, "recorded_at": iso_now()},
        headers=auth_user["headers"],
    )
    assert response.status_code == 201
    assert response.json()["total_steps"] == 2500


async def test_manual_log_steps_zero_rejected(client, auth_user):
    response = await client.post(
        "/api/v1/steps/manual", json={"steps": 0, "recorded_at": iso_now()}, headers=auth_user["headers"]
    )
    assert response.status_code == 422


async def test_manual_log_steps_over_max_rejected(client, auth_user):
    response = await client.post(
        "/api/v1/steps/manual",
        json={"steps": 100_001, "recorded_at": iso_now()},
        headers=auth_user["headers"],
    )
    assert response.status_code == 422


async def test_manual_log_called_twice_creates_two_separate_entries(client, auth_user):
    headers = auth_user["headers"]
    await client.post("/api/v1/steps/manual", json={"steps": 1000, "recorded_at": iso_now()}, headers=headers)
    second = await client.post(
        "/api/v1/steps/manual", json={"steps": 1000, "recorded_at": iso_now()}, headers=headers
    )
    assert second.json()["total_steps"] == 2000


# --------------------------------------------------------------------------
# /steps/{event_id} (DELETE)
# --------------------------------------------------------------------------

async def test_delete_nonexistent_event_returns_404(client, auth_user):
    response = await client.delete(f"/api/v1/steps/{uuid.uuid4()}", headers=auth_user["headers"])
    assert response.status_code == 404


async def test_delete_malformed_uuid_returns_422(client, auth_user):
    response = await client.delete("/api/v1/steps/not-a-uuid", headers=auth_user["headers"])
    assert response.status_code == 422


async def _latest_event_id(db_session, user_id: str) -> uuid.UUID:
    from sqlalchemy import select

    from app.models.steps import StepEvent

    event = await db_session.scalar(
        select(StepEvent)
        .where(StepEvent.user_id == uuid.UUID(user_id))
        .order_by(StepEvent.created_at.desc())
    )
    return event.id


async def test_delete_succeeds_and_removes_steps_from_today(client, auth_user, db_session):
    headers = auth_user["headers"]
    manual = await client.post(
        "/api/v1/steps/manual", json={"steps": 500, "recorded_at": iso_now()}, headers=headers
    )
    assert manual.status_code == 201
    event_id = await _latest_event_id(db_session, auth_user["user_id"])

    delete_resp = await client.delete(f"/api/v1/steps/{event_id}", headers=headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["undo_action_id"]

    today = await client.get("/api/v1/steps/today", headers=headers)
    assert today.json()["total_steps"] == 0


async def test_delete_already_deleted_event_returns_404_second_time(client, auth_user, db_session):
    headers = auth_user["headers"]
    manual = await client.post(
        "/api/v1/steps/manual", json={"steps": 500, "recorded_at": iso_now()}, headers=headers
    )
    assert manual.status_code == 201
    event_id = await _latest_event_id(db_session, auth_user["user_id"])

    first_delete = await client.delete(f"/api/v1/steps/{event_id}", headers=headers)
    second_delete = await client.delete(f"/api/v1/steps/{event_id}", headers=headers)
    assert first_delete.status_code == 200
    assert second_delete.status_code == 404


async def test_delete_another_users_event_returns_404_not_403(client, register_user, db_session):
    user_a = (await register_user()).json()
    user_b = (await register_user()).json()
    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    sync_resp = await client.post(
        "/api/v1/steps/sync",
        json={"events": [{"client_event_id": "owned-by-a", "steps_delta": 100, "recorded_at": iso_now()}]},
        headers=headers_a,
    )
    assert sync_resp.status_code == 200
    event_id = await _latest_event_id(db_session, user_a["user_id"])

    # User B must not be able to delete (or learn the existence of) an
    # event that belongs to user A - 404, not 403, so no information leak
    # about whether the id exists at all.
    delete_resp = await client.delete(f"/api/v1/steps/{event_id}", headers=headers_b)
    assert delete_resp.status_code == 404

    # Confirm it's genuinely untouched - user A can still delete it.
    delete_by_owner = await client.delete(f"/api/v1/steps/{event_id}", headers=headers_a)
    assert delete_by_owner.status_code == 200


async def test_delete_then_undo_restores_steps(client, auth_user, db_session):
    headers = auth_user["headers"]
    manual = await client.post(
        "/api/v1/steps/manual", json={"steps": 750, "recorded_at": iso_now()}, headers=headers
    )
    assert manual.json()["total_steps"] == 750
    event_id = await _latest_event_id(db_session, auth_user["user_id"])

    delete_resp = await client.delete(f"/api/v1/steps/{event_id}", headers=headers)
    assert delete_resp.status_code == 200
    undo_id = delete_resp.json()["undo_action_id"]

    after_delete = await client.get("/api/v1/steps/today", headers=headers)
    assert after_delete.json()["total_steps"] == 0

    undo_resp = await client.post(f"/api/v1/undo/{undo_id}", headers=headers)
    assert undo_resp.status_code == 204

    after_undo = await client.get("/api/v1/steps/today", headers=headers)
    assert after_undo.json()["total_steps"] == 750


# --------------------------------------------------------------------------
# /steps/today, /steps/history, /steps/daily/{date}
# --------------------------------------------------------------------------

async def test_today_with_no_activity_returns_zeroed_stats(client, auth_user):
    response = await client.get("/api/v1/steps/today", headers=auth_user["headers"])
    assert response.status_code == 200
    body = response.json()
    assert body["total_steps"] == 0
    assert body["steps_remaining"] == body["goal_steps"]
    assert body["progress_percent"] == 0.0


async def test_history_default_range_is_week(client, auth_user):
    response = await client.get("/api/v1/steps/history", headers=auth_user["headers"])
    assert response.status_code == 200
    assert isinstance(response.json(), list)


async def test_history_invalid_range_value_rejected(client, auth_user):
    response = await client.get("/api/v1/steps/history?range=decade", headers=auth_user["headers"])
    assert response.status_code == 422


@pytest.mark.parametrize("range_value", ["week", "month"])
async def test_history_accepts_valid_range_values(client, auth_user, range_value):
    response = await client.get(f"/api/v1/steps/history?range={range_value}", headers=auth_user["headers"])
    assert response.status_code == 200


async def test_daily_nonexistent_date_returns_404(client, auth_user):
    response = await client.get("/api/v1/steps/daily/2020-01-01", headers=auth_user["headers"])
    assert response.status_code == 404


async def test_daily_malformed_date_returns_422(client, auth_user):
    response = await client.get("/api/v1/steps/daily/not-a-date", headers=auth_user["headers"])
    assert response.status_code == 422


async def test_daily_invalid_calendar_date_returns_422(client, auth_user):
    response = await client.get("/api/v1/steps/daily/2026-02-30", headers=auth_user["headers"])
    assert response.status_code == 422


async def test_daily_with_real_data_returns_correct_stat(client, auth_user):
    headers = auth_user["headers"]
    today_str = datetime.now(timezone.utc).date().isoformat()
    await client.post(
        "/api/v1/steps/manual", json={"steps": 4242, "recorded_at": iso_now()}, headers=headers
    )
    response = await client.get(f"/api/v1/steps/daily/{today_str}", headers=headers)
    assert response.status_code == 200
    assert response.json()["total_steps"] == 4242


async def test_today_reflects_goal_completion_after_crossing_threshold(client, auth_user):
    headers = auth_user["headers"]
    # Default baseline goal for a user with no onboarding is 9000 (18-40,
    # lightly_active) - cross it and confirm goal_completed_at gets set.
    response = await client.post(
        "/api/v1/steps/manual", json={"steps": 9500, "recorded_at": iso_now()}, headers=headers
    )
    assert response.status_code == 201
    body = response.json()
    assert body["goal_completed_at"] is not None
    assert body["steps_remaining"] == 0
    assert body["progress_percent"] == 100.0
