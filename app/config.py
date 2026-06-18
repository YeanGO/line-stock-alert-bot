from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    line_channel_access_token: str | None = Field(default=None, alias="LINE_CHANNEL_ACCESS_TOKEN")
    line_channel_secret: str | None = Field(default=None, alias="LINE_CHANNEL_SECRET")
    database_url: str = Field(default="sqlite:///./stock_alert.db", alias="DATABASE_URL")
    monitor_interval_minutes: int = Field(default=5, alias="MONITOR_INTERVAL_MINUTES")
    monitor_interval_seconds: int | None = Field(default=90, alias="MONITOR_INTERVAL_SECONDS")
    default_cooldown_minutes: int = Field(default=20, alias="DEFAULT_COOLDOWN_MINUTES")
    dynamic_cooldown_minutes: int = Field(default=5, alias="DYNAMIC_COOLDOWN_MINUTES")
    scan_interval_seconds: int = Field(default=180, alias="SCAN_INTERVAL_SECONDS")
    batch_size: int = Field(default=80, alias="BATCH_SIZE")
    max_scan_seconds: int = Field(default=170, alias="MAX_SCAN_SECONDS")
    alert_gain_20m: float = Field(default=0.08, alias="ALERT_GAIN_20M")
    alert_volume_limit_lots: float = Field(default=2500, alias="ALERT_VOLUME_LIMIT_LOTS")
    morning_alert_type: str = Field(default="MORNING_GAIN_LOW_VOLUME", alias="MORNING_ALERT_TYPE")
    morning_scan_start: str = Field(default="09:00", alias="MORNING_SCAN_START")
    morning_scan_end: str = Field(default="13:30", alias="MORNING_SCAN_END")
    morning_scan_weekdays: str = Field(default="0,1,2,3,4", alias="MORNING_SCAN_WEEKDAYS")
    stock_symbol_suffix: str = Field(default=".TW", alias="STOCK_SYMBOL_SUFFIX")
    app_env: str = Field(default="development", alias="APP_ENV")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
