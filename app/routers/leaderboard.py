from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, DbSession
from app.schemas.leaderboard import LeaderboardResponse, LeaderboardScope
from app.services.leaderboard_service import get_leaderboard

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("", response_model=LeaderboardResponse)
async def get_leaderboard_endpoint(
    user: CurrentUser,
    db: DbSession,
    scope: LeaderboardScope = Query(default=LeaderboardScope.TODAY),
) -> LeaderboardResponse:
    entries, my_rank = await get_leaderboard(db, user, scope)
    return LeaderboardResponse(scope=scope, my_rank=my_rank, entries=entries)
