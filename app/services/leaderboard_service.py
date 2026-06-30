from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.friends import Friendship, FriendshipStatus
from app.models.settings import LeaderboardVisibility, UserSettings
from app.models.steps import DailyStat
from app.models.user import User
from app.schemas.leaderboard import LeaderboardEntry, LeaderboardScope


async def _accepted_friend_ids(db: AsyncSession, user_id: UUID) -> set[UUID]:
    rows = await db.execute(
        select(Friendship.requester_id, Friendship.addressee_id).where(
            Friendship.status == FriendshipStatus.ACCEPTED,
            or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        )
    )
    friend_ids: set[UUID] = set()
    for requester_id, addressee_id in rows.all():
        friend_ids.add(addressee_id if requester_id == user_id else requester_id)
    return friend_ids


def _scope_start_date(scope: LeaderboardScope, today: date) -> date:
    if scope == LeaderboardScope.TODAY:
        return today
    if scope == LeaderboardScope.WEEK:
        return today - timedelta(days=today.weekday())
    return today.replace(day=1)


async def get_leaderboard(
    db: AsyncSession, user: User, scope: LeaderboardScope, today: date | None = None
) -> tuple[list[LeaderboardEntry], int | None]:
    today = today or date.today()
    start_date = _scope_start_date(scope, today)

    friend_ids = await _accepted_friend_ids(db, user.id)
    candidate_ids = friend_ids | {user.id}

    # Only include candidates who haven't opted into a stricter visibility
    # than "friends" against this viewer (PUBLIC and FRIENDS both show up
    # here since the viewer is, by definition, either the user or a friend).
    visible_ids_result = await db.execute(
        select(UserSettings.user_id).where(
            UserSettings.user_id.in_(candidate_ids),
            UserSettings.leaderboard_visibility != LeaderboardVisibility.ANONYMOUS,
        )
    )
    visible_ids = {row[0] for row in visible_ids_result.all()}
    visible_ids.add(user.id)  # users always see their own entry, even if anonymous to others

    totals_result = await db.execute(
        select(DailyStat.user_id, func.coalesce(func.sum(DailyStat.total_steps), 0))
        .where(
            DailyStat.user_id.in_(visible_ids),
            DailyStat.date >= start_date,
            DailyStat.date <= today,
        )
        .group_by(DailyStat.user_id)
    )
    totals = {user_id: steps for user_id, steps in totals_result.all()}
    for user_id in visible_ids:
        totals.setdefault(user_id, 0)

    users_result = await db.execute(select(User).where(User.id.in_(visible_ids)))
    users_by_id = {u.id: u for u in users_result.scalars().all()}

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    entries = [
        LeaderboardEntry(
            rank=index + 1,
            user_id=user_id,
            display_name=(users_by_id[user_id].preferred_name or "Strack User"),
            avatar_url=users_by_id[user_id].avatar_url,
            steps=steps,
            is_self=(user_id == user.id),
        )
        for index, (user_id, steps) in enumerate(ranked)
        if user_id in users_by_id
    ]
    my_rank = next((entry.rank for entry in entries if entry.is_self), None)

    return entries, my_rank
