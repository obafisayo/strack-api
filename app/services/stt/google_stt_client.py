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

        payload = {
            "config": {
                "encoding": encoding,
                "sampleRateHertz": sample_rate_hertz,
                "languageCode": language_code,
                "enableAutomaticPunctuation": True,
            },
            "audio": {"content": base64.b64encode(audio_bytes).decode("ascii")},
        }

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
