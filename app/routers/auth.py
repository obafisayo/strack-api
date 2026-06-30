from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbSession
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.settings import UserSettings
from app.models.streaks import Streak
from app.models.user import User
from app.schemas.auth import (
    GoogleAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
)
from app.services.google_oauth import GoogleTokenError, verify_google_id_token
from app.services.username_service import generate_unique_username

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user: User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
        user_id=user.id,
    )


async def _provision_new_user(db: DbSession, **user_kwargs) -> User:
    user = User(**user_kwargs)
    db.add(user)
    await db.flush()
    db.add(UserSettings(user_id=user.id))
    db.add(Streak(user_id=user.id))
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, db: DbSession) -> TokenResponse:
    existing = await db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    username = await generate_unique_username(db, payload.email)
    user = await _provision_new_user(
        db, email=payload.email, username=username, password_hash=hash_password(payload.password)
    )
    return _issue_tokens(user)


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    user = await db.scalar(select(User).where(User.email == payload.email))
    if user is None or user.password_hash is None or not verify_password(
        payload.password, user.password_hash
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    return _issue_tokens(user)


@router.post("/google", response_model=TokenResponse)
async def google_auth(payload: GoogleAuthRequest, db: DbSession) -> TokenResponse:
    try:
        claims = verify_google_id_token(payload.id_token)
    except GoogleTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc

    google_sub = claims["sub"]
    email = claims.get("email")

    user = await db.scalar(select(User).where(User.google_sub == google_sub))
    if user is None and email:
        user = await db.scalar(select(User).where(User.email == email))
        if user is not None:
            user.google_sub = google_sub
            await db.commit()
            await db.refresh(user)

    if user is None:
        if not email:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Google account has no email")
        username = await generate_unique_username(db, email)
        user = await _provision_new_user(
            db,
            email=email,
            username=username,
            google_sub=google_sub,
            preferred_name=claims.get("name"),
            avatar_url=claims.get("picture"),
        )

    return _issue_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: DbSession) -> TokenResponse:
    try:
        user_id = decode_token(payload.refresh_token, TokenType.REFRESH)
    except InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token") from exc

    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    return _issue_tokens(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout() -> None:
    # JWTs are stateless in v1 (no server-side blacklist) - logout is purely
    # the client discarding its tokens. Endpoint kept for API symmetry / a
    # future token-revocation list.
    return None
