import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile, status
from sqlalchemy import func, or_, select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.models.friends import Friendship, FriendshipStatus
from app.models.steps import DailyStat
from app.models.streaks import Streak
from app.schemas.user import UserRead, UserStats, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])
settings = get_settings()

ALLOWED_AVATAR_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_AVATAR_BYTES = 5 * 1024 * 1024


@router.get("/me", response_model=UserRead)
async def get_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me", response_model=UserRead)
async def update_me(payload: UserUpdate, user: CurrentUser, db: DbSession) -> UserRead:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.post("/me/avatar", response_model=UserRead)
async def upload_avatar(file: UploadFile, user: CurrentUser, db: DbSession) -> UserRead:
    if file.content_type not in ALLOWED_AVATAR_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unsupported image type")

    contents = await file.read()
    if len(contents) > MAX_AVATAR_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image exceeds 5MB limit")

    extension = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[file.content_type]
    avatar_dir = Path(settings.media_root) / "avatars"
    avatar_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{user.id}.{extension}"
    (avatar_dir / filename).write_bytes(contents)

    user.avatar_url = f"{settings.base_url}{settings.media_url}/avatars/{filename}"
    await db.commit()
    await db.refresh(user)
    return UserRead.model_validate(user)


@router.get("/me/stats", response_model=UserStats)
async def get_my_stats(user: CurrentUser, db: DbSession) -> UserStats:
    total_steps = await db.scalar(
        select(func.coalesce(func.sum(DailyStat.total_steps), 0)).where(
            DailyStat.user_id == user.id
        )
    )
    best_day_steps = await db.scalar(
        select(func.coalesce(func.max(DailyStat.total_steps), 0)).where(
            DailyStat.user_id == user.id
        )
    )
    streak = await db.scalar(select(Streak).where(Streak.user_id == user.id))
    friend_count = await db.scalar(
        select(func.count())
        .select_from(Friendship)
        .where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id),
        )
    )

    return UserStats(
        total_steps=total_steps,
        best_day_steps=best_day_steps,
        longest_streak=streak.longest_streak if streak else 0,
        friend_count=friend_count,
    )
