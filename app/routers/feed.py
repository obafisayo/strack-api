import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, or_, select

from app.core.deps import CurrentUser, DbSession
from app.models.feed import FeedPost, Reaction
from app.models.friends import Friendship, FriendshipStatus
from app.models.user import User
from app.schemas.feed import FeedPostRead, FeedShareRequest, ReactionRequest
from app.services import feed_service

router = APIRouter(prefix="/feed", tags=["feed"])


async def _to_feed_post_read(db: DbSession, post: FeedPost, author: User) -> FeedPostRead:
    reaction_rows = await db.execute(
        select(Reaction.emoji, func.count())
        .where(Reaction.post_id == post.id)
        .group_by(Reaction.emoji)
    )
    reactions = {emoji: count for emoji, count in reaction_rows.all()}
    return FeedPostRead(
        id=post.id,
        user_id=post.user_id,
        display_name=author.preferred_name or author.username,
        avatar_url=author.avatar_url,
        type=post.type,
        payload=post.payload,
        created_at=post.created_at,
        reactions=reactions,
    )


@router.get("/activity", response_model=list[FeedPostRead])
async def get_activity_feed(
    user: CurrentUser, db: DbSession, limit: int = Query(default=20, ge=1, le=100)
) -> list[FeedPostRead]:
    rows = await db.scalars(
        select(FeedPost)
        .where(FeedPost.user_id == user.id)
        .order_by(FeedPost.created_at.desc())
        .limit(limit)
    )
    posts = rows.all()
    return [await _to_feed_post_read(db, post, user) for post in posts]


@router.get("/community", response_model=list[FeedPostRead])
async def get_community_feed(
    user: CurrentUser, db: DbSession, limit: int = Query(default=20, ge=1, le=100)
) -> list[FeedPostRead]:
    friend_rows = await db.execute(
        select(Friendship.requester_id, Friendship.addressee_id).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id),
        )
    )
    friend_ids = set()
    for requester_id, addressee_id in friend_rows.all():
        friend_ids.add(addressee_id if requester_id == user.id else requester_id)

    if not friend_ids:
        return []

    posts_result = await db.execute(
        select(FeedPost)
        .where(FeedPost.user_id.in_(friend_ids))
        .order_by(FeedPost.created_at.desc())
        .limit(limit)
    )
    posts = posts_result.scalars().all()

    users_result = await db.execute(select(User).where(User.id.in_(friend_ids)))
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    return [await _to_feed_post_read(db, post, users_by_id[post.user_id]) for post in posts]


@router.post("/share", response_model=FeedPostRead, status_code=status.HTTP_201_CREATED)
async def share_to_community(
    payload: FeedShareRequest, user: CurrentUser, db: DbSession
) -> FeedPostRead:
    post = await feed_service.create_community_share_post(db, user, payload.message)
    await db.commit()
    await db.refresh(post)
    return await _to_feed_post_read(db, post, user)


@router.post("/{post_id}/react", status_code=status.HTTP_204_NO_CONTENT)
async def react_to_post(
    post_id: uuid.UUID, payload: ReactionRequest, user: CurrentUser, db: DbSession
) -> None:
    post = await db.get(FeedPost, post_id)
    if post is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Post not found")

    existing = await db.scalar(
        select(Reaction).where(
            Reaction.post_id == post_id,
            Reaction.user_id == user.id,
            Reaction.emoji == payload.emoji,
        )
    )
    if existing is None:
        db.add(Reaction(post_id=post_id, user_id=user.id, emoji=payload.emoji))
        await db.commit()
