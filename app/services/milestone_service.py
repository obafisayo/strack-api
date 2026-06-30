"""Milestone detection.

The doc's "Incremental +1,000 Milestone Celebrations" describes rewarding a
1,000-step increase over a rolling daily average baseline. That requires
historical rolling-average tracking that's out of scope for this v1 scaffold;
instead we celebrate the simpler, directly observable signal of crossing each
1,000-step threshold within *today's* total, plus goal completion and
lifetime step totals (e.g. the "50k club" milestone seen in the Feed
screenshot). Swap in the rolling-average version later without touching
callers - this is the only file that decides what counts as a milestone.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.milestones import Milestone
from app.models.steps import DailyStat
from app.models.user import User
from app.services import feed_service

LIFETIME_THRESHOLDS = (50_000, 100_000, 250_000, 500_000, 1_000_000)


async def _milestone_exists(db: AsyncSession, user: User, milestone_type: str) -> bool:
    return (
        await db.scalar(
            select(Milestone.id).where(
                Milestone.user_id == user.id, Milestone.type == milestone_type
            )
        )
    ) is not None


async def check_and_record_milestones(
    db: AsyncSession, user: User, stat: DailyStat, just_completed_goal: bool
) -> list[Milestone]:
    new_milestones: list[Milestone] = []
    now = datetime.now(timezone.utc)

    daily_threshold = (stat.total_steps // 1000) * 1000
    if daily_threshold > 0:
        milestone_type = f"daily_steps_{daily_threshold}_{stat.date.isoformat()}"
        if not await _milestone_exists(db, user, milestone_type):
            new_milestones.append(
                Milestone(
                    user_id=user.id,
                    type=milestone_type,
                    achieved_at=now,
                    extra_data={"steps": daily_threshold, "date": stat.date.isoformat()},
                )
            )

    if just_completed_goal:
        milestone_type = f"goal_complete_{stat.date.isoformat()}"
        if not await _milestone_exists(db, user, milestone_type):
            new_milestones.append(
                Milestone(
                    user_id=user.id,
                    type=milestone_type,
                    achieved_at=now,
                    extra_data={"date": stat.date.isoformat(), "steps": stat.total_steps},
                )
            )

    lifetime_total = await db.scalar(
        select(func.coalesce(func.sum(DailyStat.total_steps), 0)).where(
            DailyStat.user_id == user.id
        )
    )
    for threshold in LIFETIME_THRESHOLDS:
        if lifetime_total < threshold:
            break
        milestone_type = f"lifetime_{threshold}"
        if not await _milestone_exists(db, user, milestone_type):
            new_milestones.append(
                Milestone(
                    user_id=user.id,
                    type=milestone_type,
                    achieved_at=now,
                    extra_data={"total_steps": lifetime_total},
                )
            )

    for milestone in new_milestones:
        db.add(milestone)
    if new_milestones:
        await db.flush()
        for milestone in new_milestones:
            await feed_service.create_milestone_post(db, user, milestone)

    return new_milestones
