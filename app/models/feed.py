import enum
import uuid

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin, UUIDPkMixin


class FeedPostType(str, enum.Enum):
    ACTIVITY_SUMMARY = "activity_summary"
    MILESTONE = "milestone"
    COMMUNITY_SHARE = "community_share"


class FeedPost(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "feed_posts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[FeedPostType] = mapped_column(Enum(FeedPostType, name="feed_post_type"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)


class Reaction(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "reactions"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", "emoji", name="uq_reactions_post_user_emoji"),
    )

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feed_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    emoji: Mapped[str] = mapped_column(String(16), nullable=False)
