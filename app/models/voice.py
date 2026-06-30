import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
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


class PendingVoiceConfirmation(UUIDPkMixin, TimestampMixin, Base):
    """Confirm-before-acting counterpart to UndoAction's confirm-after.

    A voice command for a destructive action (e.g. 'delete my last entry')
    doesn't act immediately - it creates a row here and asks the user to
    say a confirm/cancel phrase. The next CONFIRM intent within the expiry
    window resolves this and actually performs the action.
    """

    __tablename__ = "pending_voice_confirmations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intent: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
