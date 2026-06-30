"""Personalized daily step-goal baseline.

Per the product doc: users under 60 default to 8,000-10,000 steps, users 60+
default to 6,000-8,000 steps (the doc's intro section also mentions an
alternate 4,000-6,000 phrasing for older adults; we follow the more specific
"Dynamic Baseline Setting" feature spec here). The signup flow only collects
a 4-bucket age GROUP (under_18 / 18_40 / 41_65 / 65_plus), not exact age, so
we map 41_65 to the "under 60" bucket and 65_plus to the "60+" bucket. These
ranges are the one place to tune if that mapping needs to change.
"""

from app.models.user import ActivityLevel, AgeGroup

AGE_GROUP_STEP_RANGE: dict[AgeGroup, tuple[int, int]] = {
    AgeGroup.UNDER_18: (8_000, 10_000),
    AgeGroup.AGE_18_40: (8_000, 10_000),
    AgeGroup.AGE_41_65: (8_000, 10_000),
    AgeGroup.AGE_65_PLUS: (6_000, 8_000),
}

# Where within the age group's range the goal lands, based on self-reported
# activity level: sedentary users get the conservative low end, active users
# get the high end.
ACTIVITY_LEVEL_FACTOR: dict[ActivityLevel, float] = {
    ActivityLevel.SEDENTARY: 0.0,
    ActivityLevel.LIGHTLY_ACTIVE: 0.5,
    ActivityLevel.ACTIVE: 1.0,
}

GOAL_ROUNDING_STEP = 100


def compute_baseline_goal(age_group: AgeGroup, activity_level: ActivityLevel) -> int:
    low, high = AGE_GROUP_STEP_RANGE[age_group]
    factor = ACTIVITY_LEVEL_FACTOR[activity_level]
    raw_goal = low + (high - low) * factor
    return round(raw_goal / GOAL_ROUNDING_STEP) * GOAL_ROUNDING_STEP
