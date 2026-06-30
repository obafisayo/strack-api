import pytest

from app.services.voice_intent_service import Intent, match_intent


@pytest.mark.parametrize(
    "transcript,language,expected",
    [
        ("How many steps do I have today?", "en", Intent.QUERY_STEPS),
        ("what's my streak", "en", Intent.QUERY_STREAK),
        ("show me the leaderboard, what's my rank", "en", Intent.QUERY_LEADERBOARD),
        ("please share my progress", "en", Intent.SHARE_PROGRESS),
        ("delete my last entry", "en", Intent.DELETE_LAST_ENTRY),
        ("yes confirm", "en", Intent.CONFIRM),
        ("no, cancel that", "en", Intent.CANCEL),
        ("what's the weather like today", "en", Intent.UNKNOWN),
        ("", "en", Intent.UNKNOWN),
    ],
)
def test_match_intent_english(transcript, language, expected):
    assert match_intent(transcript, language) == expected


def test_match_intent_yoruba_steps():
    assert match_intent("Elo ni igbesẹ mi loni", "yo") == Intent.QUERY_STEPS


def test_match_intent_yoruba_confirm_ignores_tone_marks():
    # ASR output often drops tone marks - matching should still work since
    # both the transcript and keyword list are normalized before comparing.
    assert match_intent("beeni mo gba", "yo") == Intent.CONFIRM


def test_match_intent_igbo_streak():
    assert match_intent("Kedu ụbọchị m", "ig") == Intent.QUERY_STREAK


def test_match_intent_hausa_cancel():
    assert match_intent("a'a, soke shi", "ha") == Intent.CANCEL


def test_match_intent_pidgin_steps():
    assert match_intent("wetin be my steps today", "pcm") == Intent.QUERY_STEPS


def test_match_intent_unknown_language_falls_back_to_english():
    assert match_intent("how many steps", "de") == Intent.QUERY_STEPS


def test_delete_last_entry_takes_priority_over_unrelated_overlap():
    # Sanity check on the priority ordering rather than confirm/cancel
    # accidentally matching first on a longer, more specific phrase.
    assert match_intent("please delete my last entry now", "en") == Intent.DELETE_LAST_ENTRY
