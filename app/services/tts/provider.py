from abc import ABC, abstractmethod


class TTSGenerationError(Exception):
    pass


class TTSProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, language: str) -> bytes:
        """Returns the synthesized audio as raw bytes (e.g. MP3)."""
        raise NotImplementedError
