"""YarnGPT integration.

Confirmed contract (https://yarngpt.ai/api/v1/tts):
  POST, Bearer auth, JSON body {text, voice, response_format}, text <= 2000
  chars, response body is the raw audio file bytes (mp3 by default) - not a
  JSON envelope. GET https://yarngpt.ai/voices (no /api/v1 prefix) lists the
  voices actually available on this account/key.

The API has no `language` field at all - only `voice`, a fixed roster of
narrator voices. Verified live against GET /voices: this account only has
the 16 generic voices below. Earlier guidance claiming Yoruba-specific
voices ("abayomi", "aisha", "folake") does NOT match this account's real
catalogue - POSTing voice="abayomi" gets HTTP 400 "Invalid Voice". So today,
every language uses DEFAULT_VOICE; "language" only affects what `text` we
hand it (it must already be written in the target language - tone marks
included for Yoruba, e.g. à/á - since the API does not translate).

Confirmed voice names (GET /voices, 2026-06-30):
  Idera, Emma, Zainab, Osagie, Wura, Jude, Chinenye, Tayo, Regina, Femi,
  Adaora, Umar, Mary, Nonso, Remi, Adam

If language-specific voices are added to the account later, or confirmed via
GET /voices, map them in VOICE_BY_LANGUAGE below - the only place this
mapping lives.
"""

import httpx

from app.core.config import get_settings
from app.services.tts.provider import TTSGenerationError, TTSProvider

settings = get_settings()

DEFAULT_VOICE = "Idera"

VOICE_BY_LANGUAGE: dict[str, str] = {
    "en": "Idera",
    # yo, ig, ha, fr, pt, ja, tr, ar: no confirmed language-specific voice on
    # this account (GET /voices returns only the generic roster above) -
    # falls back to DEFAULT_VOICE via .get() below.
}

# YarnGPT has shown a slow cold-start on the first request after idle (30s+
# with no response), then ~3-5s on subsequent calls. Generous timeout to
# avoid spuriously failing that first request.
REQUEST_TIMEOUT_SECONDS = 60.0


class YarnGPTClient(TTSProvider):
    def __init__(self) -> None:
        self._base_url = settings.yarngpt_api_base_url
        self._api_key = settings.yarngpt_api_key

    async def synthesize(self, text: str, language: str) -> bytes:
        if not self._api_key or not self._base_url:
            raise TTSGenerationError("YarnGPT is not configured (missing API key or base URL)")

        voice = VOICE_BY_LANGUAGE.get(language, DEFAULT_VOICE)

        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            try:
                response = await client.post(
                    self._base_url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"text": text, "voice": voice, "response_format": "mp3"},
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise TTSGenerationError(
                    f"YarnGPT request failed: {exc.response.status_code} {exc.response.text}"
                ) from exc
            except httpx.HTTPError as exc:
                raise TTSGenerationError(f"YarnGPT request failed: {exc!r}") from exc

        return response.content


def get_tts_provider() -> TTSProvider:
    return YarnGPTClient()
