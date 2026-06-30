from pydantic import BaseModel

from app.models.user import ActivityLevel, AgeGroup, Gender


class OnboardingProfileRequest(BaseModel):
    preferred_name: str
    gender: Gender


class OnboardingAgeGroupRequest(BaseModel):
    age_group: AgeGroup
    activity_level: ActivityLevel = ActivityLevel.LIGHTLY_ACTIVE


class OnboardingStatusResponse(BaseModel):
    profile_completed: bool
    age_group_completed: bool
    onboarding_completed: bool
