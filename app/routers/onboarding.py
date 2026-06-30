from datetime import date, datetime, timezone

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.onboarding import (
    OnboardingAgeGroupRequest,
    OnboardingProfileRequest,
    OnboardingStatusResponse,
)
from app.services.daily_goal_service import get_or_create_daily_goal

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _status(user) -> OnboardingStatusResponse:
    profile_completed = bool(user.preferred_name and user.gender)
    age_group_completed = user.age_group is not None
    return OnboardingStatusResponse(
        profile_completed=profile_completed,
        age_group_completed=age_group_completed,
        onboarding_completed=profile_completed and age_group_completed,
    )


async def _maybe_mark_onboarding_complete(db: DbSession, user) -> None:
    status_ = _status(user)
    if status_.onboarding_completed and user.onboarding_completed_at is None:
        user.onboarding_completed_at = datetime.now(timezone.utc)
        await db.commit()


@router.post("/profile", response_model=OnboardingStatusResponse)
async def set_profile(
    payload: OnboardingProfileRequest, user: CurrentUser, db: DbSession
) -> OnboardingStatusResponse:
    user.preferred_name = payload.preferred_name
    user.gender = payload.gender
    await db.commit()
    await db.refresh(user)
    await _maybe_mark_onboarding_complete(db, user)
    return _status(user)


@router.post("/age-group", response_model=OnboardingStatusResponse)
async def set_age_group(
    payload: OnboardingAgeGroupRequest, user: CurrentUser, db: DbSession
) -> OnboardingStatusResponse:
    user.age_group = payload.age_group
    user.activity_level = payload.activity_level
    await db.commit()
    await db.refresh(user)

    # Establishes today's personalized baseline goal immediately, so the
    # home dashboard ring has a real target the moment onboarding finishes.
    await get_or_create_daily_goal(db, user, date.today())
    await db.commit()

    await _maybe_mark_onboarding_complete(db, user)
    return _status(user)


@router.get("/status", response_model=OnboardingStatusResponse)
async def get_status(user: CurrentUser) -> OnboardingStatusResponse:
    return _status(user)
