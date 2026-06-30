import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.steps import DailyStat
from app.models.streaks import Streak
from app.models.voice import VoiceClip
from app.services.tts.yarngpt_client import get_tts_provider

settings = get_settings()

# "Supported" here means selectable in the app's UI/settings, not that
# YarnGPT is confirmed to render it well - see yarngpt_client.VOICE_BY_LANGUAGE
# for which languages actually have a known-good voice today (en, yo).
SUPPORTED_LANGUAGES = [
    {"code": "en", "label": "English"},
    {"code": "yo", "label": "Yoruba"},
    {"code": "ig", "label": "Igbo"},
    {"code": "ha", "label": "Hausa"},
    {"code": "fr", "label": "Français"},
    {"code": "pt", "label": "Português"},
    {"code": "ja", "label": "日本語"},
    {"code": "tr", "label": "Türkçe"},
    {"code": "ar", "label": "العربية"},
]

STATIC_PHRASES = {
    "welcome": "Welcome to Strack. Cheers to a great start today!",
    "keep_going": "Keep it up! You're doing great today.",
}


class UnknownContextKeyError(Exception):
    pass


def resolve_context_key(context_key: str) -> str:
    try:
        return STATIC_PHRASES[context_key]
    except KeyError as exc:
        raise UnknownContextKeyError(f"Unknown context_key: {context_key!r}") from exc


def build_briefing_text(stat: DailyStat | None, goal_steps: int, streak: Streak | None) -> str:
    steps = stat.total_steps if stat else 0
    remaining = max(goal_steps - steps, 0)
    streak_days = streak.current_streak if streak else 0

    parts = [f"You've completed {steps} steps today."]
    if remaining > 0:
        parts.append(f"You have {remaining} steps remaining to reach today's goal.")
    else:
        parts.append("You've already reached today's goal. Great job!")
    if streak_days > 0:
        parts.append(f"You're on a {streak_days}-day streak.")
    return " ".join(parts)


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
