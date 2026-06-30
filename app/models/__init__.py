"""Import every model module so SQLAlchemy's mapper registry (and Alembic
autogenerate) discovers all tables via app.db.base.Base.metadata.
"""

from app.models.feed import FeedPost, Reaction  # noqa: F401
from app.models.friends import Friendship, FriendGoal  # noqa: F401
from app.models.goals import DailyGoal  # noqa: F401
from app.models.milestones import Milestone  # noqa: F401
from app.models.settings import UserSettings  # noqa: F401
from app.models.steps import DailyStat, StepEvent  # noqa: F401
from app.models.streaks import Streak  # noqa: F401
from app.models.undo import UndoAction  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.voice import VoiceClip  # noqa: F401
