import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import and_, func, or_, select

from app.core.config import get_settings
from app.core.deps import CurrentUser, DbSession
from app.models.friends import FriendGoal, Friendship, FriendshipStatus
from app.models.user import User
from app.schemas.friends import (
    FriendGoalCreate,
    FriendGoalRead,
    FriendGoalUpdate,
    FriendRead,
    FriendRequestCreate,
    FriendRequestRead,
    FriendSuggestion,
    InviteLinkResponse,
)

router = APIRouter(prefix="/friends", tags=["friends"])
settings = get_settings()


@router.get("", response_model=list[FriendRead])
async def list_friends(user: CurrentUser, db: DbSession) -> list[FriendRead]:
    rows = await db.execute(
        select(Friendship).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id),
        )
    )
    friendships = rows.scalars().all()
    friend_ids = [
        f.addressee_id if f.requester_id == user.id else f.requester_id for f in friendships
    ]
    friends_since = {
        (f.addressee_id if f.requester_id == user.id else f.requester_id): f.responded_at
        or f.created_at
        for f in friendships
    }
    if not friend_ids:
        return []

    users_result = await db.execute(select(User).where(User.id.in_(friend_ids)))
    return [
        FriendRead(
            user_id=u.id,
            display_name=u.preferred_name or u.username,
            avatar_url=u.avatar_url,
            friends_since=friends_since[u.id],
        )
        for u in users_result.scalars().all()
    ]


@router.get("/requests", response_model=list[FriendRequestRead])
async def list_friend_requests(user: CurrentUser, db: DbSession) -> list[FriendRequestRead]:
    rows = await db.scalars(
        select(Friendship).where(
            Friendship.addressee_id == user.id, Friendship.status == FriendshipStatus.PENDING
        )
    )
    friendships = rows.all()
    if not friendships:
        return []

    requester_ids = {f.requester_id for f in friendships}
    users_result = await db.execute(select(User).where(User.id.in_(requester_ids)))
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    results = []
    for f in friendships:
        requester = users_by_id.get(f.requester_id)
        results.append(
            FriendRequestRead(
                id=f.id,
                requester_id=f.requester_id,
                addressee_id=f.addressee_id,
                status=f.status,
                created_at=f.created_at,
                display_name=(requester.preferred_name or requester.username)
                if requester
                else None,
                avatar_url=requester.avatar_url if requester else None,
            )
        )
    return results


@router.post(
    "/requests", response_model=FriendRequestRead, status_code=status.HTTP_201_CREATED
)
async def send_friend_request(
    payload: FriendRequestCreate, user: CurrentUser, db: DbSession
) -> FriendRequestRead:
    if payload.user_id is not None:
        target = await db.get(User, payload.user_id)
    else:
        # Case-insensitive, trimmed search so "Alice@Example.com" finds "alice@example.com"
        identifier = payload.username_or_email.strip().lower()
        target = await db.scalar(
            select(User).where(
                or_(
                    func.lower(User.username) == identifier,
                    func.lower(User.email) == identifier,
                )
            )
        )
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No user found with that username or email")
    if target.id == user.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You can't friend yourself")

    existing = await db.scalar(
        select(Friendship).where(
            or_(
                and_(Friendship.requester_id == user.id, Friendship.addressee_id == target.id),
                and_(Friendship.requester_id == target.id, Friendship.addressee_id == user.id),
            )
        )
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A friend request already exists")

    friendship = Friendship(requester_id=user.id, addressee_id=target.id)
    db.add(friendship)
    await db.commit()
    await db.refresh(friendship)
    return FriendRequestRead(
        id=friendship.id,
        requester_id=friendship.requester_id,
        addressee_id=friendship.addressee_id,
        status=friendship.status,
        created_at=friendship.created_at,
        display_name=user.preferred_name or user.username,
        avatar_url=user.avatar_url,
    )


async def _respond_to_request(
    request_id: uuid.UUID, user: CurrentUser, db: DbSession, accept: bool
) -> None:
    friendship = await db.get(Friendship, request_id)
    if (
        friendship is None
        or friendship.addressee_id != user.id
        or friendship.status != FriendshipStatus.PENDING
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Friend request not found")

    friendship.status = FriendshipStatus.ACCEPTED if accept else FriendshipStatus.DECLINED
    friendship.responded_at = datetime.now(timezone.utc)
    await db.commit()


@router.post("/requests/{request_id}/accept", status_code=status.HTTP_204_NO_CONTENT)
async def accept_friend_request(request_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await _respond_to_request(request_id, user, db, accept=True)


@router.post("/requests/{request_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
async def decline_friend_request(request_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    await _respond_to_request(request_id, user, db, accept=False)


@router.delete("/{friend_user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_friend(friend_user_id: uuid.UUID, user: CurrentUser, db: DbSession) -> None:
    friendship = await db.scalar(
        select(Friendship).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(
                and_(
                    Friendship.requester_id == user.id, Friendship.addressee_id == friend_user_id
                ),
                and_(
                    Friendship.requester_id == friend_user_id, Friendship.addressee_id == user.id
                ),
            ),
        )
    )
    if friendship is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Friendship not found")
    await db.delete(friendship)
    await db.commit()


@router.get("/suggestions", response_model=list[FriendSuggestion])
async def get_suggestions(user: CurrentUser, db: DbSession) -> list[FriendSuggestion]:
    existing_rows = await db.execute(
        select(Friendship.requester_id, Friendship.addressee_id).where(
            or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id)
        )
    )
    excluded_ids = {user.id}
    for requester_id, addressee_id in existing_rows.all():
        excluded_ids.add(requester_id)
        excluded_ids.add(addressee_id)

    rows = await db.execute(select(User).where(User.id.notin_(excluded_ids)).limit(10))
    return [
        FriendSuggestion(
            user_id=u.id,
            username=u.username,
            display_name=u.preferred_name or u.username,
            avatar_url=u.avatar_url,
        )
        for u in rows.scalars().all()
    ]


@router.post("/invite", response_model=InviteLinkResponse)
async def create_invite_link(user: CurrentUser) -> InviteLinkResponse:
    invite_code = secrets.token_urlsafe(8)
    return InviteLinkResponse(
        invite_code=invite_code,
        invite_url=f"{settings.base_url}/invite/{invite_code}",
    )


# --- Friend goals -----------------------------------------------------------

friend_goals_router = APIRouter(prefix="/friend-goals", tags=["friend-goals"])


@friend_goals_router.post("", response_model=FriendGoalRead, status_code=status.HTTP_201_CREATED)
async def create_friend_goal(
    payload: FriendGoalCreate, user: CurrentUser, db: DbSession
) -> FriendGoalRead:
    friendship = await db.scalar(
        select(Friendship).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(
                and_(
                    Friendship.requester_id == user.id,
                    Friendship.addressee_id == payload.friend_user_id,
                ),
                and_(
                    Friendship.requester_id == payload.friend_user_id,
                    Friendship.addressee_id == user.id,
                ),
            ),
        )
    )
    if friendship is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You must be friends to set a shared goal")

    goal = FriendGoal(
        user_a_id=user.id,
        user_b_id=payload.friend_user_id,
        target_steps=payload.target_steps,
        start_date=payload.start_date,
    )
    db.add(goal)
    await db.commit()
    await db.refresh(goal)
    return FriendGoalRead.model_validate(goal)


@friend_goals_router.get("", response_model=list[FriendGoalRead])
async def list_friend_goals(user: CurrentUser, db: DbSession) -> list[FriendGoalRead]:
    rows = await db.scalars(
        select(FriendGoal).where(
            or_(FriendGoal.user_a_id == user.id, FriendGoal.user_b_id == user.id)
        )
    )
    return [FriendGoalRead.model_validate(row) for row in rows.all()]


@friend_goals_router.patch("/{goal_id}", response_model=FriendGoalRead)
async def update_friend_goal(
    goal_id: uuid.UUID, payload: FriendGoalUpdate, user: CurrentUser, db: DbSession
) -> FriendGoalRead:
    goal = await db.get(FriendGoal, goal_id)
    if goal is None or user.id not in (goal.user_a_id, goal.user_b_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Friend goal not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(goal, field, value)
    await db.commit()
    await db.refresh(goal)
    return FriendGoalRead.model_validate(goal)
