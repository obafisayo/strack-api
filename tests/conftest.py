"""Shared fixtures for endpoint (HTTP) tests.

CRITICAL ORDERING: app.db.base creates its async engine at import time, bound
to whatever DATABASE_URL is in the environment at that moment (and
app.core.config.get_settings() is @lru_cache'd, so whichever value wins
first sticks for the rest of the process). Every env var override below
MUST happen before any `from app...` import - that's why they're at module
level, ahead of the app imports a few lines down, not inside a fixture.

SAFETY: the project's .env DATABASE_URL has previously pointed at the Render
*production* database (see git history / chat - it was switched there for
deploy debugging). Tests truncate tables before every run. The test DB URL
below is therefore built from the local POSTGRES_* values, never from
DATABASE_URL itself, with asserts that refuse to run against anything that
isn't an explicit local `strack_test` database.
"""

import os
import uuid
from pathlib import Path

from dotenv import dotenv_values

_env_file = Path(__file__).resolve().parent.parent / ".env"
_env_values = dotenv_values(_env_file)

_pg_user = _env_values.get("POSTGRES_USER", "strack")
_pg_password = _env_values.get("POSTGRES_PASSWORD", "strack")
_pg_port = _env_values.get("POSTGRES_PORT", "5432")
TEST_DATABASE_URL = f"postgresql+asyncpg://{_pg_user}:{_pg_password}@localhost:{_pg_port}/strack_test"

assert "localhost" in TEST_DATABASE_URL, "Refusing to run tests against a non-localhost database"
assert TEST_DATABASE_URL.rsplit("/", 1)[-1] == "strack_test", (
    "Refusing to run tests against a database not named strack_test"
)

os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["JWT_SECRET_KEY"] = "test-secret-key-for-pytest-only"
os.environ["DEBUG"] = "false"
# Force-blank any real external credentials so a test that forgets to stub a
# provider fails loudly (provider raises "not configured") instead of
# silently making a real, billed network call.
os.environ["GOOGLE_APPLICATION_CREDENTIALS_JSON"] = ""
os.environ["GOOGLE_CLIENT_ID"] = ""
os.environ["YARNGPT_API_KEY"] = ""

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.base import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.stt.provider import STTProvider  # noqa: E402
from app.services.tts.provider import TTSProvider  # noqa: E402


class FakeTTSProvider(TTSProvider):
    """Deterministic stand-in for YarnGPT - tests assert on OUR logic, not a
    third-party API's reliability or cost real money per test run."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.audio_bytes = b"FAKE_MP3_BYTES"
        self.error: Exception | None = None

    async def synthesize(self, text: str, language: str) -> bytes:
        self.calls.append((text, language))
        if self.error is not None:
            raise self.error
        return self.audio_bytes


class FakeSTTProvider(STTProvider):
    """Deterministic stand-in for Google Speech-to-Text. `transcript` is
    settable per-test so the intent-matching/dispatch logic downstream of
    transcription can be tested without real audio or real network calls."""

    def __init__(self) -> None:
        self.calls: list[tuple[bytes, str, int, str]] = []
        self.transcript = ""
        self.error: Exception | None = None

    async def transcribe(
        self, audio_bytes: bytes, encoding: str, sample_rate_hertz: int, language: str
    ) -> str:
        self.calls.append((audio_bytes, encoding, sample_rate_hertz, language))
        if self.error is not None:
            raise self.error
        return self.transcript


@pytest.fixture(scope="session", autouse=True)
async def _create_schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


@pytest.fixture(autouse=True)
async def _clean_db():
    """Truncates every app table before each test for isolation. Runs
    before, not after, so a failed test's leftover data never bleeds into
    the next one (and the DB is inspectable after a failure for debugging).
    """
    table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
async def db_session():
    """Raw DB access for test setup/verification that has no corresponding
    public endpoint (e.g. looking up a StepEvent's id - nothing in the API
    returns individual event ids, only DailyStat aggregates). Not used to
    bypass the endpoint under test, only to arrange/inspect state around it.
    """
    from app.db.base import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def stub_tts_provider(monkeypatch):
    fake = FakeTTSProvider()
    monkeypatch.setattr("app.services.voice_service.get_tts_provider", lambda: fake)
    return fake


@pytest.fixture
def stub_stt_provider(monkeypatch):
    fake = FakeSTTProvider()
    monkeypatch.setattr("app.routers.voice.get_stt_provider", lambda: fake)
    return fake


def unique_email() -> str:
    return f"test+{uuid.uuid4().hex[:12]}@example.com"


@pytest.fixture
def register_user(client):
    async def _register(email: str | None = None, password: str = "TestPassword123", **extra):
        payload = {"email": email or unique_email(), "password": password, **extra}
        return await client.post("/api/v1/auth/register", json=payload)

    return _register


@pytest.fixture
async def auth_user(register_user):
    """Registers a fresh user and returns its id/tokens/ready-to-use auth
    header - the common case most endpoint tests need."""
    response = await register_user()
    data = response.json()
    return {
        "user_id": data["user_id"],
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
    }
