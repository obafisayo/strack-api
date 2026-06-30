from pydantic import BaseModel, Field, model_validator


class VoiceLanguage(BaseModel):
    code: str
    label: str


class VoiceSpeakRequest(BaseModel):
    text: str | None = Field(default=None, max_length=2000)  # YarnGPT's hard text limit
    context_key: str | None = Field(default=None, max_length=50)
    language: str = "en"

    @model_validator(mode="after")
    def _require_text_or_context(self) -> "VoiceSpeakRequest":
        if not self.text and not self.context_key:
            raise ValueError("Either 'text' or 'context_key' must be provided")
        return self


class VoiceSpeakResponse(BaseModel):
    text: str
    language: str
    audio_url: str
    cached: bool


class VoiceListenResponse(BaseModel):
    transcript: str
    language: str
    intent: str
    response_text: str
    audio_url: str
    result: dict | None = None
