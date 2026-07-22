"""Google Cloud Speech-to-Text integration.

Verified directly against Google's own docs (2026-06-30): the v1 REST API
officially supports yo-NG (Yoruba), ig-NG (Igbo), and ha-NG (Hausa).
Nigerian Pidgin has no dedicated model anywhere we found, so it's mapped to
en-NG (English-Nigeria) as the closest approximation - Pidgin is
English-derived, so this is a reasonable fallback, not a confirmed-good fit.

We call the REST API directly via httpx rather than installing the full
google-cloud-speech SDK: a service-account JSON key (pasted whole into
GOOGLE_APPLICATION_CREDENTIALS_JSON, since Render has no persistent
filesystem to point a credentials file at) is exchanged for a bearer token
using google-auth - a dependency we already have for verifying Google
Sign-In tokens (see app/services/google_oauth.py).

Synchronous `recognize` (not the streaming or long-running APIs) is used
since voice commands are short clips - well under its ~1 minute/10MB limit.
"""

import asyncio
import base64
import json

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from app.core.config import get_settings
from app.services.stt.provider import STTProvider, STTTranscriptionError

settings = get_settings()

RECOGNIZE_URL = "https://speech.googleapis.com/v1/speech:recognize"
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

LANGUAGE_CODE_BY_APP_LANGUAGE: dict[str, str] = {
    "en": "en-NG",
    "yo": "yo-NG",
    "ig": "ig-NG",
    "ha": "ha-NG",
    "pcm": "en-NG",  # Nigerian Pidgin - no dedicated model, closest fallback
}
DEFAULT_LANGUAGE_CODE = "en-NG"

# Vocabulary hints sent to Google STT so its acoustic model scores our command
# words higher than generic speech. Written in the plain form Google STT itself
# returns for each language (yo-NG/ig-NG/ha-NG transcripts drop tone marks, so
# diacritics would never match the incoming transcript anyway).
_SPEECH_HINTS: dict[str, list[str]] = {
    "yo-NG": [
        # steps / walking
        "igbese", "igbese mi", "kini igbese", "kini igbese mi",
        "elo igbese mi", "melo igbese", "mo ti rin", "irin ajo mi",
        # streak / days
        "ojo mi", "streak mi", "owoowoomi", "ojo owoowoomi",
        # leaderboard / rank
        "ipo mi", "adije", "leaderboard",
        # share / delete
        "pin ilosiwaju mi", "ilosiwaju mi", "pa igbese", "yo igbese",
        # confirm / cancel
        "beeni", "rara", "fagile",
    ],
    "ig-NG": [
        # steps
        "nzoukwu", "nzoukwu m", "ole nzoukwu m", "nzoukwu m taa",
        # streak
        "usoro ubochi", "usoro ubochi m", "ubochi m", "ole ubochi",
        # leaderboard
        "onodu", "onodu m", "ebe m no",
        # share / delete
        "kesaa oganihu m", "oganihu m", "hichapu ndenye", "wepu ndenye",
        # confirm / cancel
        "ee", "kwado", "o di mma", "mba", "kagbuo",
    ],
    "ha-NG": [
        # steps
        "matakai", "matakaina", "matakai na", "matakai nawa",
        "yaya matakaina", "nawa matakaina ne",
        # streak
        "jerin kwanaki", "jerin kwanaki nawa", "jerina", "kwanaki nawa",
        # leaderboard
        "matsayi", "matsayina", "matsayi nawa", "ina na tsaya",
        # share / delete
        "raba ci gaba", "raba ci gabana", "goge shigarwa", "share shigarwa ta karshe",
        # confirm / cancel
        "tabbatar", "i tabbatar", "soke", "a'a",
    ],
    "en-NG": [
        # covers both "en" and "pcm" (Nigerian Pidgin)
        "steps", "my steps", "step count", "how many steps", "steps today",
        "streak", "my streak", "how many days",
        "leaderboard", "my rank", "my position",
        "share my progress", "post my progress",
        "delete my last entry", "delete last entry", "undo last step",
        "yes", "confirm", "okay", "no", "cancel",
        # Pidgin-specific
        "waka", "how many step i waka", "wetin be my steps", "how my steps be",
        "na so", "i confam", "abeg no",
    ],
}

# Nigerian languages frequently mix in English words ("streak mi", "leaderboard").
# Adding en-NG as an alternative lets Google recognise those tokens in context.
_ALTERNATIVE_LANGUAGE_CODES: dict[str, list[str]] = {
    "yo-NG": ["en-NG"],
    "ig-NG": ["en-NG"],
    "ha-NG": ["en-NG"],
}

# Module-level so the minted access token (valid ~1hr) is reused across
# requests instead of being re-derived from the service account key every
# time get_stt_provider() is called.
_credentials: service_account.Credentials | None = None


def _get_credentials() -> service_account.Credentials:
    global _credentials
    if _credentials is None:
        if not settings.google_application_credentials_json:
            raise STTTranscriptionError(
                "Google STT is not configured (missing GOOGLE_APPLICATION_CREDENTIALS_JSON)"
            )
        try:
            info = json.loads(settings.google_application_credentials_json)
        except json.JSONDecodeError as exc:
            raise STTTranscriptionError(
                "GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON"
            ) from exc
        _credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    return _credentials


class GoogleSTTClient(STTProvider):
    async def _get_access_token(self) -> str:
        credentials = _get_credentials()
        if not credentials.valid:
            # google-auth's refresh() is a blocking network call - push it
            # off the event loop rather than stalling every other request.
            await asyncio.to_thread(credentials.refresh, Request())
        return credentials.token

    async def transcribe(
        self, audio_bytes: bytes, encoding: str, sample_rate_hertz: int, language: str
    ) -> str:
        access_token = await self._get_access_token()
        language_code = LANGUAGE_CODE_BY_APP_LANGUAGE.get(language, DEFAULT_LANGUAGE_CODE)

        payload: dict = {
            "config": {
                "encoding": encoding,
                "sampleRateHertz": sample_rate_hertz,
                "languageCode": language_code,
                "enableAutomaticPunctuation": True,
            },
            "audio": {"content": base64.b64encode(audio_bytes).decode("ascii")},
        }

        hints = _SPEECH_HINTS.get(language_code, [])
        if hints:
            payload["config"]["speechContexts"] = [{"phrases": hints, "boost": 15}]

        alt_codes = _ALTERNATIVE_LANGUAGE_CODES.get(language_code, [])
        if alt_codes:
            payload["config"]["alternativeLanguageCodes"] = alt_codes

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    RECOGNIZE_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                    json=payload,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise STTTranscriptionError(
                    f"Google STT request failed: {exc.response.status_code} {exc.response.text}"
                ) from exc
            except httpx.HTTPError as exc:
                raise STTTranscriptionError(f"Google STT request failed: {exc!r}") from exc

        data = response.json()
        results = data.get("results", [])
        transcript_parts = [
            result["alternatives"][0]["transcript"]
            for result in results
            if result.get("alternatives")
        ]
        return " ".join(transcript_parts).strip()


def get_stt_provider() -> STTProvider:
    return GoogleSTTClient()
