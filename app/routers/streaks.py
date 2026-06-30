from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.schemas.streaks import StreakRead
from app.services.streak_service import get_or_create_streak

router = APIRouter(prefix="/streaks", tags=["streaks"])


@router.get("/me", response_model=StreakRead)
async def get_my_streak(user: CurrentUser, db: DbSession) -> StreakRead:
    streak = await get_or_create_streak(db, user)
    await db.commit()
    return StreakRead.model_validate(streak)
