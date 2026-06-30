"""Adversarial endpoint tests for POST /voice/listen.

Uses stub_stt_provider/stub_tts_provider (see conftest.py) instead of real
Google STT/YarnGPT - tests exhaustively cover OUR logic (upload validation,
intent dispatch, confirm/cancel races, cross-user isolation) deterministically
and for free, not third-party transcription accuracy.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _files(content: bytes = b"fake-audio-bytes", filename: str = "clip.mp3"):
    return {"audio": (filename, content, "audio/mpeg")}


async def test_listen_requires_auth(client, stub_stt_provider):
    response = await client.post("/api/v1/voice/listen", files=_files(), data={"language": "en"})
    assert response.status_code == 401


async def test_listen_empty_audio_file_rejected(client, auth_user, stub_stt_provider):
    response = await client.post(
        "/api/v1/voice/listen",
        files=_files(content=b""),
        data={"language": "en"},
        headers=auth_user["headers"],
    )
    assert response.status_code == 400


async def test_listen_oversized_audio_file_rejected(client, auth_user, stub_stt_provider):
    too_big = b"x" * (10 * 1024 * 1024 + 1)
    response = await client.post(
        "/api/v1/voice/listen",
        files=_files(content=too_big),
        data={"language": "en"},
        headers=auth_user["headers"],
    )
    assert response.status_code == 400


async def test_listen_audio_exactly_at_10mb_boundary_accepted(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "how many steps"
    exactly_10mb = b"x" * (10 * 1024 * 1024)
    response = await client.post(
        "/api/v1/voice/listen",
        files=_files(content=exactly_10mb),
        data={"language": "en"},
        headers=auth_user["headers"],
    )
    assert response.status_code == 200


async def test_listen_missing_audio_field_entirely_rejected(client, auth_user, stub_stt_provider):
    response = await client.post(
        "/api/v1/voice/listen", data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 422


async def test_listen_no_speech_recognized_returns_422(client, auth_user, stub_stt_provider):
    stub_stt_provider.transcript = ""
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 422


async def test_listen_stt_provider_error_returns_502(client, auth_user, stub_stt_provider):
    from app.services.stt.provider import STTTranscriptionError

    stub_stt_provider.error = STTTranscriptionError("simulated Google STT outage")
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 502


async def test_listen_tts_provider_error_on_reply_still_returns_502(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    # The action (e.g. a query) already executed successfully by the time
    # the reply's TTS call fails - this documents that real, slightly odd
    # edge case rather than assuming the whole request rolls back cleanly.
    from app.services.tts.provider import TTSGenerationError

    stub_stt_provider.transcript = "how many steps"
    stub_tts_provider.error = TTSGenerationError("simulated YarnGPT outage")
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 502


@pytest.mark.parametrize(
    "transcript,language,expected_intent",
    [
        pytest.param("how many steps do I have today", "en", "query_steps", id="en-query-steps"),
        pytest.param("what's my streak", "en", "query_streak", id="en-query-streak"),
        pytest.param("show me the leaderboard", "en", "query_leaderboard", id="en-query-leaderboard"),
        pytest.param("share my progress", "en", "share_progress", id="en-share-progress"),
        pytest.param("delete my last entry", "en", "delete_last_entry", id="en-delete-last-entry"),
        pytest.param("elo ni igbesẹ mi", "yo", "query_steps", id="yo-query-steps"),
        pytest.param("nawa matakai na", "ha", "query_steps", id="ha-query-steps-split-tokenization"),
        pytest.param("wetin be my steps today", "pcm", "query_steps", id="pcm-query-steps"),
        pytest.param("asdkfj qwoeiru random gibberish", "en", "unknown", id="en-gibberish-unknown"),
        pytest.param("", "en", "unknown", id="empty-string-defensive"),
    ],
)
async def test_listen_dispatches_correct_intent(
    client, auth_user, stub_stt_provider, stub_tts_provider, transcript, language, expected_intent
):
    stub_stt_provider.transcript = transcript
    response = await client.post(
        "/api/v1/voice/listen",
        files=_files(),
        data={"language": language},
        headers=auth_user["headers"],
    )
    if transcript == "":
        assert response.status_code == 422
        return
    assert response.status_code == 200
    assert response.json()["intent"] == expected_intent


async def test_listen_reply_audio_is_localized_not_english_for_non_english_language(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "elo ni igbesẹ mi"
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "yo"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    # The text actually handed to the (stubbed) TTS provider must not be the
    # English template - this is exactly the bug found and fixed earlier in
    # this session (voice_action_service was hardcoded to English).
    assert stub_tts_provider.calls
    spoken_text, spoken_language = stub_tts_provider.calls[-1]
    assert spoken_language == "yo"
    assert "You've completed" not in spoken_text
    assert "ìgbésẹ̀" in spoken_text or "igbesẹ" in spoken_text.lower()


async def test_listen_confirm_with_no_pending_action(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "yes confirm"
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "confirm"
    assert response.json()["result"] is None


async def test_listen_cancel_with_no_pending_action(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "no cancel"
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "cancel"


async def test_listen_delete_then_confirm_full_flow(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    headers = auth_user["headers"]
    await client.post(
        "/api/v1/steps/manual", json={"steps": 1234, "recorded_at": iso_now()}, headers=headers
    )

    stub_stt_provider.transcript = "delete my last entry"
    delete_resp = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers
    )
    assert delete_resp.status_code == 200
    assert delete_resp.json()["intent"] == "delete_last_entry"
    assert delete_resp.json()["result"]["steps_delta"] == 1234

    stub_stt_provider.transcript = "yes confirm"
    confirm_resp = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers
    )
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["intent"] == "confirm"
    assert confirm_resp.json()["result"]["deleted_steps"] == 1234

    today = await client.get("/api/v1/steps/today", headers=headers)
    assert today.json()["total_steps"] == 0


async def test_listen_delete_then_cancel_does_not_delete(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    headers = auth_user["headers"]
    await client.post(
        "/api/v1/steps/manual", json={"steps": 999, "recorded_at": iso_now()}, headers=headers
    )

    stub_stt_provider.transcript = "delete my last entry"
    await client.post("/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers)

    stub_stt_provider.transcript = "no cancel"
    cancel_resp = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers
    )
    assert cancel_resp.json()["intent"] == "cancel"
    assert cancel_resp.json()["response_text"]

    today = await client.get("/api/v1/steps/today", headers=headers)
    assert today.json()["total_steps"] == 999


async def test_listen_double_confirm_race_second_finds_nothing(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    headers = auth_user["headers"]
    await client.post(
        "/api/v1/steps/manual", json={"steps": 500, "recorded_at": iso_now()}, headers=headers
    )
    stub_stt_provider.transcript = "delete my last entry"
    await client.post("/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers)

    stub_stt_provider.transcript = "yes confirm"
    first = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers
    )
    second = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers
    )
    assert first.json()["result"]["deleted_steps"] == 500
    assert second.json()["result"] is None


async def test_listen_pending_confirmation_is_per_user_not_global(
    client, register_user, stub_stt_provider, stub_tts_provider
):
    user_a = (await register_user()).json()
    user_b = (await register_user()).json()
    headers_a = {"Authorization": f"Bearer {user_a['access_token']}"}
    headers_b = {"Authorization": f"Bearer {user_b['access_token']}"}

    await client.post(
        "/api/v1/steps/manual", json={"steps": 321, "recorded_at": iso_now()}, headers=headers_a
    )
    stub_stt_provider.transcript = "delete my last entry"
    await client.post("/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers_a)

    # User B confirming must not resolve user A's pending action.
    stub_stt_provider.transcript = "yes confirm"
    b_confirm = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=headers_b
    )
    assert b_confirm.json()["result"] is None

    a_today = await client.get("/api/v1/steps/today", headers=headers_a)
    assert a_today.json()["total_steps"] == 321


async def test_listen_concurrent_listen_requests_for_same_user(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "how many steps"
    responses = await asyncio.gather(
        *[
            client.post(
                "/api/v1/voice/listen",
                files=_files(),
                data={"language": "en"},
                headers=auth_user["headers"],
            )
            for _ in range(5)
        ]
    )
    assert all(r.status_code == 200 for r in responses)
    assert all(r.json()["intent"] == "query_steps" for r in responses)


async def test_listen_unknown_language_falls_back_gracefully(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "how many steps"
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "de"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "query_steps"


async def test_listen_extremely_long_transcript_handled(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "how many steps " + ("filler word " * 500)
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "query_steps"


async def test_listen_transcript_with_mixed_intent_keywords_uses_priority_order(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    # Contains both a query-steps-shaped phrase and the word "yes" - per
    # _INTENT_PRIORITY, the more specific query intent should win, not the
    # short, easily-false-positive CONFIRM keyword.
    stub_stt_provider.transcript = "yes how many steps do I have"
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "query_steps"


async def test_listen_unicode_and_emoji_in_transcript_does_not_crash(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "how many steps 👟🏃💨 今日は"
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200


async def test_listen_zero_and_negative_sample_rate_still_processed(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    # The value is opaque to us - it's only ever forwarded to the STT
    # provider (stubbed here), so there's nothing for our own validation to
    # reject; documents that we don't gatekeep it ourselves.
    stub_stt_provider.transcript = "how many steps"
    response = await client.post(
        "/api/v1/voice/listen",
        files=_files(),
        data={"language": "en", "sample_rate_hertz": "0"},
        headers=auth_user["headers"],
    )
    assert response.status_code == 200

    stub_stt_provider.calls.clear()
    response_negative = await client.post(
        "/api/v1/voice/listen",
        files=_files(),
        data={"language": "en", "sample_rate_hertz": "-16000"},
        headers=auth_user["headers"],
    )
    assert response_negative.status_code == 200


async def test_listen_non_integer_sample_rate_rejected(client, auth_user, stub_stt_provider):
    response = await client.post(
        "/api/v1/voice/listen",
        files=_files(),
        data={"language": "en", "sample_rate_hertz": "not-a-number"},
        headers=auth_user["headers"],
    )
    assert response.status_code == 422


async def test_listen_arbitrary_encoding_string_forwarded_as_is(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "how many steps"
    response = await client.post(
        "/api/v1/voice/listen",
        files=_files(),
        data={"language": "en", "encoding": "SOME_MADE_UP_CODEC"},
        headers=auth_user["headers"],
    )
    assert response.status_code == 200
    assert stub_stt_provider.calls[-1][1] == "SOME_MADE_UP_CODEC"


async def test_listen_default_language_is_english_when_omitted(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "how many steps"
    response = await client.post("/api/v1/voice/listen", files=_files(), headers=auth_user["headers"])
    assert response.status_code == 200
    assert response.json()["language"] == "en"


async def test_listen_garbage_bearer_token_rejected(client, stub_stt_provider):
    response = await client.post(
        "/api/v1/voice/listen",
        files=_files(),
        data={"language": "en"},
        headers={"Authorization": "Bearer garbage-not-a-jwt"},
    )
    assert response.status_code == 401


async def test_listen_share_progress_intent_creates_feed_post(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "share my progress"
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    assert response.json()["result"]["post_id"]

    feed = await client.get("/api/v1/feed/activity", headers=auth_user["headers"])
    assert feed.status_code == 200


async def test_listen_delete_with_no_step_entries_at_all(
    client, auth_user, stub_stt_provider, stub_tts_provider
):
    stub_stt_provider.transcript = "delete my last entry"
    response = await client.post(
        "/api/v1/voice/listen", files=_files(), data={"language": "en"}, headers=auth_user["headers"]
    )
    assert response.status_code == 200
    assert response.json()["intent"] == "delete_last_entry"
    assert response.json()["result"] is None
