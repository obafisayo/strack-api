import pytest

from app.models.user import ActivityLevel, AgeGroup
from app.services.goal_service import compute_baseline_goal


@pytest.mark.parametrize(
    "age_group,activity_level,expected",
    [
        (AgeGroup.AGE_18_40, ActivityLevel.SEDENTARY, 8_000),
        (AgeGroup.AGE_18_40, ActivityLevel.LIGHTLY_ACTIVE, 9_000),
        (AgeGroup.AGE_18_40, ActivityLevel.ACTIVE, 10_000),
        (AgeGroup.UNDER_18, ActivityLevel.ACTIVE, 10_000),
        (AgeGroup.AGE_41_65, ActivityLevel.SEDENTARY, 8_000),
        (AgeGroup.AGE_65_PLUS, ActivityLevel.SEDENTARY, 6_000),
        (AgeGroup.AGE_65_PLUS, ActivityLevel.LIGHTLY_ACTIVE, 7_000),
        (AgeGroup.AGE_65_PLUS, ActivityLevel.ACTIVE, 8_000),
    ],
)
def test_compute_baseline_goal(age_group, activity_level, expected):
    assert compute_baseline_goal(age_group, activity_level) == expected
