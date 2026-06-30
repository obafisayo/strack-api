from pydantic import BaseModel, ConfigDict

from app.models.settings import AlertChannel, FontSize, LeaderboardVisibility, Theme, Units


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    font_size: FontSize
    theme: Theme
    notifications_enabled: bool
    voice_assistant_enabled: bool
    alert_channel: AlertChannel
    language: str
    units: Units
    leaderboard_visibility: LeaderboardVisibility


class SettingsUpdate(BaseModel):
    font_size: FontSize | None = None
    theme: Theme | None = None
    notifications_enabled: bool | None = None
    voice_assistant_enabled: bool | None = None
    alert_channel: AlertChannel | None = None
    language: str | None = None
    units: Units | None = None
    leaderboard_visibility: LeaderboardVisibility | None = None
