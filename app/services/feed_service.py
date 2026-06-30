from sqlalchemy.ext.asyncio import AsyncSession

from app.models.feed import FeedPost, FeedPostType
from app.models.milestones import Milestone
from app.models.steps import DailyStat
from app.models.user import User


async def create_activity_summary_post(db: AsyncSession, user: User, stat: DailyStat) -> FeedPost:
    post = FeedPost(
        user_id=user.id,
        type=FeedPostType.ACTIVITY_SUMMARY,
        payload={
            "date": stat.date.isoformat(),
            "steps": stat.total_steps,
            "distance_km": stat.distance_km,
            "calories": stat.calories,
        },
    )
    db.add(post)
    await db.flush()
    return post


async def create_milestone_post(db: AsyncSession, user: User, milestone: Milestone) -> FeedPost:
    post = FeedPost(
        user_id=user.id,
        type=FeedPostType.MILESTONE,
        payload={"milestone_type": milestone.type, **milestone.extra_data},
    )
    db.add(post)
    await db.flush()
    return post


async def create_community_share_post(
    db: AsyncSession, user: User, message: str | None
) -> FeedPost:
    post = FeedPost(
        user_id=user.id,
        type=FeedPostType.COMMUNITY_SHARE,
        payload={"message": message} if message else {},
    )
    db.add(post)
    await db.flush()
    return post
