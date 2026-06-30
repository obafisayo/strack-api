# STRACK API

FastAPI + Postgres backend for STRACK, an accessible step-tracking app. This
repo is backend-only; the Expo (React Native) client is built separately and
talks to this API over `Authorization: Bearer <JWT>`.

## Stack

- FastAPI + Uvicorn
- SQLAlchemy 2.0 (async, asyncpg) + Alembic migrations
- Postgres 16
- JWT auth (email/password + Google Sign-In), bcrypt password hashing
- YarnGPT for multilingual voice-assistant audio

## Running locally

```bash
cp .env.example .env   # fill in JWT_SECRET_KEY, GOOGLE_CLIENT_ID, YARNGPT_API_KEY
docker compose up --build
```

This starts Postgres, runs `alembic upgrade head`, and serves the API at
`http://localhost:8000`. Interactive docs: `http://localhost:8000/docs`.

### Creating a new migration after changing models

```bash
docker compose run --rm api alembic revision --autogenerate -m "describe the change"
docker compose run --rm api alembic upgrade head
```

### Running tests

Tests cover pure business logic only (goal baseline calculation, streak
transitions, undo expiry) - no database required:

```bash
pip install -e ".[dev]"
pytest
```

## Project layout

```
app/
  core/       settings, JWT/password security, get_db & get_current_user deps
  db/         SQLAlchemy engine/session/declarative base
  models/     ORM models (one file per domain)
  schemas/    Pydantic request/response models
  services/   business logic: goal baselines, step aggregation, streaks,
              milestones, undo, leaderboard, friends/google-oauth helpers,
              and the YarnGPT TTS client
  routers/    one APIRouter per domain, all mounted under /api/v1
alembic/      migrations
tests/        unit tests for the services layer
```

## API surface

All endpoints are under `/api/v1` and (except `/auth/*`) require a Bearer
access token.

| Domain | Endpoints |
|---|---|
| Auth | `POST /auth/register`, `/login`, `/google`, `/refresh`, `/logout` |
| Onboarding | `POST /onboarding/profile`, `/age-group`, `GET /onboarding/status` |
| Users | `GET/PATCH /users/me`, `POST /users/me/avatar`, `GET /users/me/stats` |
| Settings | `GET/PATCH /settings` (font size, theme, alerts channel, language, units, leaderboard visibility) |
| Goals | `GET/PATCH /goals/today`, `GET /goals/history` |
| Steps | `POST /steps/sync`, `/manual`, `DELETE /steps/{id}`, `GET /steps/today`, `/history`, `/daily/{date}` |
| Undo | `POST /undo/{undo_action_id}` (5-second window) |
| Streaks | `GET /streaks/me` |
| Milestones | `GET /milestones` |
| Leaderboard | `GET /leaderboard?scope=today\|week\|month` |
| Friends | `GET /friends`, `/requests`, `POST /requests`, `/requests/{id}/accept\|decline`, `DELETE /friends/{id}`, `GET /suggestions`, `POST /invite` |
| Friend goals | `POST/GET /friend-goals`, `PATCH /friend-goals/{id}` |
| Feed | `GET /feed/activity`, `/community`, `POST /feed/share`, `POST /feed/{id}/react` |
| Voice | `GET /voice/languages`, `POST /voice/speak`, `GET /voice/briefing` |
| Sync | `GET /sync/status` |

## Known gaps / things to revisit

- **YarnGPT voice coverage**: confirmed, good-quality voices only exist for
  English (`Idera` etc.) and Yoruba (`abayomi`, `aisha`, `folake`). Igbo,
  Hausa, French, Portuguese, Japanese, Turkish, and Arabic fall back to the
  English voice until real voice names for those languages are confirmed -
  see `app/services/tts/yarngpt_client.py`.
- **Milestone detection** celebrates crossing 1,000-step thresholds within a
  single day, goal completion, and lifetime totals - not the literal
  "1,000 steps over your rolling daily average baseline" described in the
  product doc, which needs historical rolling-average tracking out of scope
  for v1. See `app/services/milestone_service.py`.
- **Leaderboard updates** are request/response (poll `GET /leaderboard`),
  not push/websocket, despite the doc describing it as "live."
- Distance/calorie/active-minute conversions in `step_aggregation.py` are
  rough constants (not biometrically personalized) - fine for the "Real-World
  Data Formatter" feature, easy to tune later.
