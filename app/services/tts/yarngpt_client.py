"""YarnGPT integration.

Confirmed contract (https://yarngpt.ai/api/v1/tts):
  POST, Bearer auth, JSON body {text, voice, response_format}, text <= 2000
  chars, response body is the raw audio file bytes (mp3 by default) - not a
  JSON envelope.

The API has no separate `language` field - the spoken language comes from
two things together: (1) the `text` itself must already be written in that
language (for Yoruba, ideally with tone marks - à, á - for accurate
pronunciation), and (2) a `voice` matching that language, since voices are
themselves language-specific speakers, not generic narrators.

Confirmed voice names:
  - English (generic):  Idera, Emma, Zainab, Osagie, Wura, Jude, Chinenye,
                         Tayo, Regina, Femi, Adaora, Umar, Mary, Nonso,
                         Remi, Adam
  - Yoruba:              abayomi, aisha, folake

We do NOT have confirmed voice names for Igbo, Hausa, French, Portuguese,
Japanese, Turkish, or Arabic - YarnGPT's voice catalogue so far looks
Nigerian-language-focused, so it's possible some of those (fr/pt/ja/tr/ar in
particular) aren't supported by this provider at all. Until confirmed, any
language without a known voice falls back to DEFAULT_VOICE, which will
mispronounce non-English/non-Yoruba text - this is a known gap, not a bug.
Update VOICE_BY_LANGUAGE here (the only place this mapping lives) once more
voice names are confirmed.
"""

import httpx

from app.core.config import get_settings
from app.services.tts.provider import TTSGenerationError, TTSProvider

settings = get_settings()

DEFAULT_VOICE = "Idera"

VOICE_BY_LANGUAGE: dict[str, str] = {
    "en": "Idera",
    "yo": "abayomi",
    # ig, ha, fr, pt, ja, tr, ar: no confirmed voice name yet - falls back
    # to DEFAULT_VOICE via .get() below.
}


class YarnGPTClient(TTSProvider):
    def __init__(self) -> None:
        self._base_url = settings.yarngpt_api_base_url
        self._api_key = settings.yarngpt_api_key

    async def synthesize(self, text: str, language: str) -> bytes:
        if not self._api_key or not self._base_url:
            raise TTSGenerationError("YarnGPT is not configured (missing API key or base URL)")

        voice = VOICE_BY_LANGUAGE.get(language, DEFAULT_VOICE)

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    self._base_url,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                    json={"text": text, "voice": voice, "response_format": "mp3"},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise TTSGenerationError(f"YarnGPT request failed: {exc}") from exc

        return response.content


def get_tts_provider() -> TTSProvider:
    return YarnGPTClient()
