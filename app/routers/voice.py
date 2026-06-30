from datetime import date

from fastapi import APIRouter, Form, HTTPException, UploadFile, status

from app.core.deps import CurrentUser, DbSession
from app.schemas.voice import (
    VoiceLanguage,
    VoiceListenResponse,
    VoiceSpeakRequest,
    VoiceSpeakResponse,
)
from app.services import step_aggregation, streak_service, voice_action_service, voice_service
from app.services.daily_goal_service import get_or_create_daily_goal
from app.services.stt.google_stt_client import get_stt_provider
from app.services.stt.provider import STTTranscriptionError
from app.services.tts.provider import TTSGenerationError
from app.services.voice_intent_service import match_intent

router = APIRouter(prefix="/voice", tags=["voice"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # Google's synchronous recognize limit


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


@router.post("/listen", response_model=VoiceListenResponse)
async def listen(
    user: CurrentUser,
    db: DbSession,
    audio: UploadFile,
    language: str = Form(default="en"),
    encoding: str = Form(default="LINEAR16"),
    sample_rate_hertz: int = Form(default=16000),
) -> VoiceListenResponse:
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No audio data received")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Audio exceeds 10MB limit")

    stt_provider = get_stt_provider()
    try:
        transcript = await stt_provider.transcribe(
            audio_bytes, encoding, sample_rate_hertz, language
        )
    except STTTranscriptionError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    if not transcript:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "Could not recognize any speech in the audio"
        )

    intent = match_intent(transcript, language)
    response_text, result = await voice_action_service.execute(db, user, intent)

    try:
        audio_url, _cached = await voice_service.get_or_create_clip(db, response_text, language)
    except TTSGenerationError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    await db.commit()
    return VoiceListenResponse(
        transcript=transcript,
        language=language,
        intent=intent.value,
        response_text=response_text,
        audio_url=audio_url,
        result=result,
    )
