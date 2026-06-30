from abc import ABC, abstractmethod


class STTTranscriptionError(Exception):
    pass


class STTProvider(ABC):
    @abstractmethod
    async def transcribe(
        self, audio_bytes: bytes, encoding: str, sample_rate_hertz: int, language: str
    ) -> str:
        """Returns the transcribed text, or an empty string if nothing was recognized."""
        raise NotImplementedError
