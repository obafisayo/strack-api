"""Adversarial endpoint tests for /auth/* - register, login, google, refresh.

Organized as large parametrized tables (the maintainable way to express many
distinct edge cases) plus a handful of standalone behavioral tests for things
that need actual state (duplicate registration, token reuse, races).
"""

import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import TokenType, create_access_token, create_refresh_token

settings = get_settings()

VALID_PASSWORD = "ValidPassword123"


# --------------------------------------------------------------------------
# /auth/register - payloads that must be rejected with 422
# --------------------------------------------------------------------------

INVALID_REGISTER_PAYLOADS = [
    pytest.param({"password": VALID_PASSWORD}, id="missing-email"),
    pytest.param({"email": "test@example.com"}, id="missing-password"),
    pytest.param({}, id="empty-body"),
    pytest.param({"email": None, "password": VALID_PASSWORD}, id="null-email"),
    pytest.param({"email": "test@example.com", "password": None}, id="null-password"),
    pytest.param({"email": "not-an-email", "password": VALID_PASSWORD}, id="email-no-at-sign"),
    pytest.param({"email": "@example.com", "password": VALID_PASSWORD}, id="email-empty-local-part"),
    pytest.param({"email": "test@", "password": VALID_PASSWORD}, id="email-empty-domain"),
    pytest.param({"email": "test@@example.com", "password": VALID_PASSWORD}, id="email-double-at"),
    pytest.param({"email": "test @example.com", "password": VALID_PASSWORD}, id="email-internal-space"),
    pytest.param({"email": " test@example.com", "password": VALID_PASSWORD}, id="email-leading-space"),
    pytest.param({"email": "test@example.com ", "password": VALID_PASSWORD}, id="email-trailing-space"),
    pytest.param({"email": "test\n@example.com", "password": VALID_PASSWORD}, id="email-embedded-newline"),
    pytest.param({"email": "test\x00@example.com", "password": VALID_PASSWORD}, id="email-null-byte"),
    pytest.param({"email": "', OR '1'='1@example.com", "password": VALID_PASSWORD}, id="email-sql-injection-shaped"),
    pytest.param({"email": "x" * 250 + "@example.com", "password": VALID_PASSWORD}, id="email-extremely-long-local-part"),
    pytest.param({"email": 12345, "password": VALID_PASSWORD}, id="email-wrong-type-int"),
    pytest.param({"email": ["test@example.com"], "password": VALID_PASSWORD}, id="email-wrong-type-array"),
    pytest.param({"email": {"value": "test@example.com"}, "password": VALID_PASSWORD}, id="email-wrong-type-object"),
    pytest.param({"email": "test@example.com", "password": "short12"}, id="password-7-chars-below-min"),
    pytest.param({"email": "test@example.com", "password": "x" * 129}, id="password-129-chars-above-max"),
    pytest.param({"email": "test@example.com", "password": ""}, id="password-empty-string"),
    pytest.param({"email": "test@example.com", "password": "   "}, id="password-whitespace-only-short"),
    pytest.param({"email": "test@example.com", "password": 12345678}, id="password-wrong-type-int"),
    pytest.param({"email": "test@example.com", "password": ["password123"]}, id="password-wrong-type-array"),
    pytest.param({"email": "test@example.com", "password": True}, id="password-wrong-type-bool"),
    pytest.param("not-a-json-object", id="body-is-bare-string"),
    pytest.param(["test@example.com", VALID_PASSWORD], id="body-is-array-not-object"),
    pytest.param(None, id="body-is-null"),
]


@pytest.mark.parametrize("payload", INVALID_REGISTER_PAYLOADS)
async def test_register_rejects_invalid_payload(client, payload):
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 422


# --------------------------------------------------------------------------
# /auth/register - payloads that are unusual but VALID (must succeed)
# --------------------------------------------------------------------------

VALID_EDGE_REGISTER_PAYLOADS = [
    pytest.param({"password": "exactly8"}, id="password-exactly-8-chars-min-boundary"),
    pytest.param({"password": "x" * 128}, id="password-exactly-128-chars-max-boundary"),
    pytest.param({"password": "🔒🔑💪🎉emoji9"}, id="password-with-emoji"),
    pytest.param({"password": "Sénhä123 müller"}, id="password-with-unicode-and-space"),
    pytest.param({"email": "user+tag@example.com", "password": VALID_PASSWORD}, id="email-plus-addressing"),
    pytest.param({"email": "user.name@example.co.uk", "password": VALID_PASSWORD}, id="email-multi-level-domain"),
    pytest.param({"email": "üser@example.com", "password": VALID_PASSWORD}, id="email-unicode-local-part"),
]


@pytest.mark.parametrize("extra", VALID_EDGE_REGISTER_PAYLOADS)
async def test_register_accepts_valid_edge_case(client, extra):
    payload = {"email": extra.get("email") or f"edge+{uuid.uuid4().hex[:8]}@example.com", **extra}
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["user_id"]


async def test_register_ignores_unexpected_extra_fields(client):
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"extra+{uuid.uuid4().hex[:8]}@example.com",
            "password": VALID_PASSWORD,
            "is_admin": True,
            "role": "superuser",
            "unexpected_field": ["anything"],
        },
    )
    assert response.status_code == 201


async def test_register_duplicate_email_is_rejected(client, register_user):
    email = f"dup+{uuid.uuid4().hex[:8]}@example.com"
    first = await register_user(email=email)
    assert first.status_code == 201

    second = await register_user(email=email)
    assert second.status_code == 409


async def test_register_duplicate_email_different_case_still_rejected_or_succeeds_consistently(
    client, register_user
):
    # Documents actual behavior rather than assuming it: email uniqueness in
    # this schema is a plain DB equality check, not case-folded - so
    # Test@Example.com and test@example.com are currently DIFFERENT users.
    # This isn't necessarily a bug, but it's a real, worth-knowing fact.
    base = uuid.uuid4().hex[:8]
    lower = await register_user(email=f"case{base}@example.com")
    upper = await register_user(email=f"CASE{base}@example.com")
    assert lower.status_code == 201
    assert upper.status_code == 201
    assert lower.json()["user_id"] != upper.json()["user_id"]


async def test_register_concurrent_same_email_only_one_succeeds(client, register_user):
    import asyncio

    email = f"race+{uuid.uuid4().hex[:8]}@example.com"
    responses = await asyncio.gather(
        register_user(email=email), register_user(email=email), register_user(email=email)
    )
    status_codes = sorted(r.status_code for r in responses)
    assert status_codes.count(201) == 1
    assert all(code in (201, 409) for code in status_codes)


async def test_register_response_never_includes_password_hash(client, register_user):
    response = await register_user()
    assert "password" not in response.text
    assert "password_hash" not in response.text


# --------------------------------------------------------------------------
# /auth/login
# --------------------------------------------------------------------------

INVALID_LOGIN_PAYLOADS = [
    pytest.param({"password": VALID_PASSWORD}, id="login-missing-email"),
    pytest.param({"email": "test@example.com"}, id="login-missing-password"),
    pytest.param({}, id="login-empty-body"),
    pytest.param({"email": "not-an-email", "password": VALID_PASSWORD}, id="login-malformed-email"),
    pytest.param(None, id="login-null-body"),
]


@pytest.mark.parametrize("payload", INVALID_LOGIN_PAYLOADS)
async def test_login_rejects_invalid_payload(client, payload):
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 422


WRONG_CREDENTIAL_CASES = [
    pytest.param("wrong-password", id="wrong-password"),
    pytest.param(VALID_PASSWORD + " ", id="correct-password-plus-trailing-space"),
    pytest.param(" " + VALID_PASSWORD, id="correct-password-plus-leading-space"),
    pytest.param(VALID_PASSWORD.lower(), id="correct-password-wrong-case"),
    pytest.param("", id="empty-password-against-real-account"),
    pytest.param(VALID_PASSWORD[:-1], id="correct-password-missing-last-char"),
]


@pytest.mark.parametrize("bad_password", WRONG_CREDENTIAL_CASES)
async def test_login_rejects_wrong_password(client, register_user, bad_password):
    email = f"wrongpw+{uuid.uuid4().hex[:8]}@example.com"
    reg = await register_user(email=email, password=VALID_PASSWORD)
    assert reg.status_code == 201

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": bad_password})
    assert response.status_code == 401


async def test_login_nonexistent_email_returns_401_not_404(client):
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": f"nobody+{uuid.uuid4().hex[:8]}@example.com", "password": VALID_PASSWORD},
    )
    # Must not leak whether the account exists via a different status code.
    assert response.status_code == 401


async def test_login_error_message_identical_for_wrong_password_and_unknown_email(client, register_user):
    email = f"enum+{uuid.uuid4().hex[:8]}@example.com"
    await register_user(email=email, password=VALID_PASSWORD)

    wrong_password_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "wrong"}
    )
    unknown_email_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": f"unknown+{uuid.uuid4().hex[:8]}@example.com", "password": VALID_PASSWORD},
    )
    assert wrong_password_resp.json()["detail"] == unknown_email_resp.json()["detail"]


async def test_login_succeeds_with_correct_credentials(client, register_user):
    email = f"goodlogin+{uuid.uuid4().hex[:8]}@example.com"
    await register_user(email=email, password=VALID_PASSWORD)

    response = await client.post("/api/v1/auth/login", json={"email": email, "password": VALID_PASSWORD})
    assert response.status_code == 200
    assert response.json()["access_token"]


async def test_login_against_google_only_account_with_no_password_fails_cleanly(client, monkeypatch):
    # A Google-provisioned account has password_hash=None - logging in with
    # any password must fail gracefully, not crash on a None comparison.
    email = f"googleonly+{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(
        "app.routers.auth.verify_google_id_token",
        lambda token: {"sub": f"google-{uuid.uuid4().hex}", "email": email, "name": "G User"},
    )
    google_resp = await client.post("/api/v1/auth/google", json={"id_token": "irrelevant-stub-value"})
    assert google_resp.status_code == 200

    login_resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "anything-at-all"}
    )
    assert login_resp.status_code == 401


# --------------------------------------------------------------------------
# /auth/refresh
# --------------------------------------------------------------------------

def _expired_token(user_id: uuid.UUID, token_type: TokenType) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now - timedelta(hours=2),
        "exp": now - timedelta(hours=1),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _wrong_secret_token(user_id: uuid.UUID, token_type: TokenType) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + timedelta(days=1),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, "wrong-secret-key", algorithm=settings.jwt_algorithm)


def _none_alg_token(user_id: uuid.UUID, token_type: TokenType) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": token_type.value,
        "iat": now,
        "exp": now + timedelta(days=1),
    }
    return jwt.encode(payload, "", algorithm="none")


def _malformed_subject_token(token_type: TokenType) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "not-a-valid-uuid",
        "type": token_type.value,
        "iat": now,
        "exp": now + timedelta(days=1),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


async def test_refresh_rejects_garbage_string(client):
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-jwt-at-all"})
    assert response.status_code == 401


async def test_refresh_rejects_empty_string(client):
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": ""})
    assert response.status_code == 401


async def test_refresh_rejects_missing_field(client):
    response = await client.post("/api/v1/auth/refresh", json={})
    assert response.status_code == 422


async def test_refresh_rejects_expired_token(client, register_user):
    reg = await register_user()
    user_id = uuid.UUID(reg.json()["user_id"])
    token = _expired_token(user_id, TokenType.REFRESH)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_refresh_rejects_token_signed_with_wrong_secret(client, register_user):
    reg = await register_user()
    user_id = uuid.UUID(reg.json()["user_id"])
    token = _wrong_secret_token(user_id, TokenType.REFRESH)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_refresh_rejects_alg_none_token(client, register_user):
    reg = await register_user()
    user_id = uuid.UUID(reg.json()["user_id"])
    token = _none_alg_token(user_id, TokenType.REFRESH)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_refresh_rejects_access_token_used_as_refresh_token(client, register_user):
    reg = await register_user()
    access_token = reg.json()["access_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
    assert response.status_code == 401


async def test_refresh_rejects_token_with_malformed_subject(client):
    token = _malformed_subject_token(TokenType.REFRESH)
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_refresh_rejects_token_for_deleted_or_nonexistent_user(client):
    token = create_refresh_token(uuid.uuid4())
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert response.status_code == 401


async def test_refresh_rejects_tampered_payload_bit_flip(client, register_user):
    reg = await register_user()
    user_id = reg.json()["user_id"]
    token = create_refresh_token(uuid.UUID(user_id))

    header, payload, signature = token.split(".")
    # Flip the last character of the payload segment - corrupts the
    # base64url content, which must fail signature verification.
    tampered_char = "A" if payload[-1] != "A" else "B"
    tampered_payload = payload[:-1] + tampered_char
    tampered_token = f"{header}.{tampered_payload}.{signature}"

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": tampered_token})
    assert response.status_code == 401


async def test_refresh_succeeds_with_valid_token_and_returns_new_tokens(client, register_user):
    reg = await register_user()
    refresh_token = reg.json()["refresh_token"]

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]


async def test_refresh_can_be_reused_multiple_times_documents_no_rotation(client, register_user):
    # Documents actual behavior: refresh tokens are NOT single-use/rotated
    # in v1 (no server-side blacklist - see logout()'s own comment). Using
    # the same refresh token twice both succeed. Not asserted as "correct"
    # security design, just the real current behavior.
    reg = await register_user()
    refresh_token = reg.json()["refresh_token"]

    first = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    second = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert first.status_code == 200
    assert second.status_code == 200


async def test_refresh_token_with_far_future_iat_still_processed(client, register_user):
    reg = await register_user()
    user_id = uuid.UUID(reg.json()["user_id"])
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "type": TokenType.REFRESH.value,
        "iat": now + timedelta(days=3650),
        "exp": now + timedelta(days=3651),
        "jti": str(uuid.uuid4()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    # PyJWT doesn't reject a future iat by default - documents that this
    # passes rather than assuming it's rejected.
    assert response.status_code == 200


# --------------------------------------------------------------------------
# /auth/google - Google ID token verification is monkeypatched so tests run
# offline/free, deterministically. See conftest.py's stub philosophy.
# --------------------------------------------------------------------------

async def test_google_auth_creates_new_user(client, monkeypatch):
    email = f"newgoogle+{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(
        "app.routers.auth.verify_google_id_token",
        lambda token: {"sub": "google-sub-12345", "email": email, "name": "Test User"},
    )
    response = await client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 200
    assert response.json()["user_id"]


async def test_google_auth_links_existing_email_account(client, register_user, monkeypatch):
    email = f"linkme+{uuid.uuid4().hex[:8]}@example.com"
    reg = await register_user(email=email)
    existing_user_id = reg.json()["user_id"]

    monkeypatch.setattr(
        "app.routers.auth.verify_google_id_token",
        lambda token: {"sub": "google-sub-link-test", "email": email, "name": "Linked"},
    )
    response = await client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 200
    assert response.json()["user_id"] == existing_user_id


async def test_google_auth_same_sub_returns_same_user_idempotently(client, monkeypatch):
    email = f"idempotent+{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(
        "app.routers.auth.verify_google_id_token",
        lambda token: {"sub": "google-sub-idempotent", "email": email, "name": "Idempotent"},
    )
    first = await client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    second = await client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert first.json()["user_id"] == second.json()["user_id"]


async def test_google_auth_rejects_invalid_token(client, monkeypatch):
    from app.services.google_oauth import GoogleTokenError

    def _raise(token):
        raise GoogleTokenError("Token verification failed")

    monkeypatch.setattr("app.routers.auth.verify_google_id_token", _raise)
    response = await client.post("/api/v1/auth/google", json={"id_token": "invalid"})
    assert response.status_code == 401


async def test_google_auth_rejects_account_with_no_email(client, monkeypatch):
    monkeypatch.setattr(
        "app.routers.auth.verify_google_id_token",
        lambda token: {"sub": "google-sub-no-email"},
    )
    response = await client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 400


async def test_google_auth_missing_id_token_field_is_422(client):
    response = await client.post("/api/v1/auth/google", json={})
    assert response.status_code == 422


async def test_google_auth_empty_string_id_token(client, monkeypatch):
    from app.services.google_oauth import GoogleTokenError

    def _raise(token):
        raise GoogleTokenError("empty token")

    monkeypatch.setattr("app.routers.auth.verify_google_id_token", _raise)
    response = await client.post("/api/v1/auth/google", json={"id_token": ""})
    assert response.status_code == 401


async def test_google_auth_with_unicode_name_and_picture_url(client, monkeypatch):
    email = f"unicode+{uuid.uuid4().hex[:8]}@example.com"
    monkeypatch.setattr(
        "app.routers.auth.verify_google_id_token",
        lambda token: {
            "sub": "google-sub-unicode",
            "email": email,
            "name": "Ọláyínká 用户 🎉",
            "picture": "https://example.com/avatar.jpg?param=日本語",
        },
    )
    response = await client.post("/api/v1/auth/google", json={"id_token": "fake-token"})
    assert response.status_code == 200
