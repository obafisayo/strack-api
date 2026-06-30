from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.routers import (
    auth,
    feed,
    friends,
    goals,
    leaderboard,
    milestones,
    onboarding,
    settings as settings_router,
    steps,
    streaks,
    sync,
    undo,
    users,
    voice,
)

settings = get_settings()

app = FastAPI(title="STRACK API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(settings.media_url, StaticFiles(directory=settings.media_root), name="media")

API_PREFIX = "/api/v1"

for router in (
    auth.router,
    onboarding.router,
    users.router,
    settings_router.router,
    goals.router,
    steps.router,
    undo.router,
    streaks.router,
    milestones.router,
    leaderboard.router,
    friends.router,
    friends.friend_goals_router,
    feed.router,
    voice.router,
    sync.router,
):
    app.include_router(router, prefix=API_PREFIX)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
