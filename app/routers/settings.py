from fastapi import APIRouter
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession
from app.models.settings import UserSettings
from app.schemas.settings import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


async def _get_settings_row(db: DbSession, user) -> UserSettings:
    settings_row = await db.scalar(select(UserSettings).where(UserSettings.user_id == user.id))
    if settings_row is None:
        settings_row = UserSettings(user_id=user.id)
        db.add(settings_row)
        await db.commit()
        await db.refresh(settings_row)
    return settings_row


@router.get("", response_model=SettingsRead)
async def get_settings_endpoint(user: CurrentUser, db: DbSession) -> SettingsRead:
    return SettingsRead.model_validate(await _get_settings_row(db, user))


@router.patch("", response_model=SettingsRead)
async def update_settings_endpoint(
    payload: SettingsUpdate, user: CurrentUser, db: DbSession
) -> SettingsRead:
    settings_row = await _get_settings_row(db, user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings_row, field, value)
    await db.commit()
    await db.refresh(settings_row)
    return SettingsRead.model_validate(settings_row)
