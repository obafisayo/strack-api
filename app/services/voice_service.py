import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.steps import DailyStat
from app.models.streaks import Streak
from app.models.voice import VoiceClip
from app.services.tts.yarngpt_client import get_tts_provider
from app.services.voice_localization import t

settings = get_settings()

# "Supported" here means selectable in the app's UI/settings, not that
# YarnGPT is confirmed to render it well - see yarngpt_client.VOICE_BY_LANGUAGE
# for which languages actually have a known-good voice today (en, yo).
SUPPORTED_LANGUAGES = [
    {"code": "en", "label": "English"},
    {"code": "yo", "label": "Yoruba"},
    {"code": "ig", "label": "Igbo"},
    {"code": "ha", "label": "Hausa"},
    {"code": "pcm", "label": "Nigerian Pidgin"},
    {"code": "fr", "label": "Français"},
    {"code": "pt", "label": "Português"},
    {"code": "ja", "label": "日本語"},
    {"code": "tr", "label": "Türkçe"},
    {"code": "ar", "label": "العربية"},
]

# Context keys map straight onto voice_localization template keys, so the
# same translated phrase is reused by both /voice/speak?context_key=... and
# the action dispatcher (e.g. "welcome" is also used as an onboarding cue).
STATIC_CONTEXT_KEYS = {"welcome", "keep_going"}


class UnknownContextKeyError(Exception):
    pass


def resolve_context_key(context_key: str, language: str) -> str:
    if context_key not in STATIC_CONTEXT_KEYS:
        raise UnknownContextKeyError(f"Unknown context_key: {context_key!r}")
    return t(language, context_key)


def build_briefing_text(
    stat: DailyStat | None, goal_steps: int, streak: Streak | None, language: str
) -> str:
    steps = stat.total_steps if stat else 0
    remaining = max(goal_steps - steps, 0)
    streak_days = streak.current_streak if streak else 0

    text = (
        t(language, "steps_remaining", steps=steps, remaining=remaining)
        if remaining > 0
        else t(language, "steps_goal_reached", steps=steps)
    )
    if streak_days > 0:
        text += " " + t(language, "briefing_streak", days=streak_days)
    return text


async def get_or_create_clip(db: AsyncSession, text: str, language: str) -> tuple[str, bool]:
    text_hash = hashlib.sha256(f"{language}:{text}".encode("utf-8")).hexdigest()

    existing = await db.scalar(
        select(VoiceClip).where(VoiceClip.text_hash == text_hash, VoiceClip.language == language)
    )
    if existing is not None:
        return existing.audio_url, True

    provider = get_tts_provider()
    audio_bytes = await provider.synthesize(text, language)

    audio_dir = Path(settings.media_root) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{text_hash}.mp3"
    (audio_dir / filename).write_bytes(audio_bytes)

    audio_url = f"{settings.base_url}{settings.media_url}/audio/{filename}"

    db.add(VoiceClip(text_hash=text_hash, language=language, text=text, audio_url=audio_url))
    await db.flush()

    return audio_url, False
