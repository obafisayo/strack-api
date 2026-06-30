from datetime import date

from fastapi import APIRouter, HTTPException, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.voice import VoiceLanguage, VoiceSpeakRequest, VoiceSpeakResponse
from app.services import step_aggregation, streak_service, voice_service
from app.services.daily_goal_service import get_or_create_daily_goal
from app.services.tts.provider import TTSGenerationError

router = APIRouter(prefix="/voice", tags=["voice"])


@router.get("/languages", response_model=list[VoiceLanguage])
async def get_languages() -> list[VoiceLanguage]:
    return [VoiceLanguage(**lang) for lang in voice_service.SUPPORTED_LANGUAGES]


@router.post("/speak", response_model=VoiceSpeakResponse)
async def speak(payload: VoiceSpeakRequest, db: DbSession) -> VoiceSpeakResponse:
    if payload.text:
        text = payload.text
    else:
        try:
            text = voice_service.resolve_context_key(payload.context_key)
        except voice_service.UnknownContextKeyError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    try:
        audio_url, cached = await voice_service.get_or_create_clip(db, text, payload.language)
    except TTSGenerationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()
    return VoiceSpeakResponse(text=text, language=payload.language, audio_url=audio_url, cached=cached)


@router.get("/briefing", response_model=VoiceSpeakResponse)
async def get_briefing(user: CurrentUser, db: DbSession, language: str = "en") -> VoiceSpeakResponse:
    today = date.today()
    stat = await step_aggregation.get_daily_stat(db, user, today)
    goal = await get_or_create_daily_goal(db, user, today)
    streak = await streak_service.get_or_create_streak(db, user)
    await db.commit()

    text = voice_service.build_briefing_text(stat, goal.goal_steps, streak)

    try:
        audio_url, cached = await voice_service.get_or_create_clip(db, text, language)
    except TTSGenerationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()
    return VoiceSpeakResponse(text=text, language=language, audio_url=audio_url, cached=cached)
