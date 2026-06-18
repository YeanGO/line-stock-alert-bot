from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WatchlistCreate(BaseModel):
    line_user_id: str
    line_target_id: str | None = None
    target_type: str = "user"
    created_by_user_id: str | None = None
    stock_symbol: str
    stock_name: str | None = None
    condition_type: str
    target_price: float | None = None
    target_percent: float | None = None
    target_multiplier: float | None = None
    ma_period: int | None = None
    window_minutes: int | None = None
    max_volume_lots: float | None = None
    active_weekdays: str | None = None
    monitor_start_time: str | None = None
    monitor_end_time: str | None = None
    cooldown_minutes: int


class WatchlistRead(WatchlistCreate):
    id: int
    is_active: bool
    last_triggered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
