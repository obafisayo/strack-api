import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.mixins import UUIDPkMixin

if TYPE_CHECKING:
    from app.models.user import User


class FontSize(str, enum.Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class Theme(str, enum.Enum):
    LIGHT = "light"
    DARK = "dark"


class AlertChannel(str, enum.Enum):
    AUDIO = "audio"
    HAPTIC = "haptic"
    VISUAL = "visual"
    ALL = "all"


class LeaderboardVisibility(str, enum.Enum):
    PUBLIC = "public"
    FRIENDS = "friends"
    ANONYMOUS = "anonymous"


class Units(str, enum.Enum):
    KM = "km"
    MI = "mi"


class UserSettings(UUIDPkMixin, Base):
    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )

    font_size: Mapped[FontSize] = mapped_column(
        Enum(FontSize, name="font_size"), default=FontSize.MEDIUM, nullable=False
    )
    theme: Mapped[Theme] = mapped_column(Enum(Theme, name="theme"), default=Theme.LIGHT, nullable=False)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    voice_assistant_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    alert_channel: Mapped[AlertChannel] = mapped_column(
        Enum(AlertChannel, name="alert_channel"), default=AlertChannel.ALL, nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    units: Mapped[Units] = mapped_column(Enum(Units, name="units"), default=Units.KM, nullable=False)
    leaderboard_visibility: Mapped[LeaderboardVisibility] = mapped_column(
        Enum(LeaderboardVisibility, name="leaderboard_visibility"),
        default=LeaderboardVisibility.FRIENDS,
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="settings")
