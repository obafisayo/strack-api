from sqlalchemy import String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class VoiceClip(UUIDPkMixin, TimestampMixin, Base):
    """Cache of generated TTS clips, keyed by the hash of (text, language), so
    repeated phrases (milestone lines, morning briefings) don't re-hit YarnGPT.
    """

    __tablename__ = "voice_clips"
    __table_args__ = (UniqueConstraint("text_hash", "language", name="uq_voice_clips_text_lang"),)

    text_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(String(1000), nullable=False)
    audio_url: Mapped[str] = mapped_column(String(500), nullable=False)
