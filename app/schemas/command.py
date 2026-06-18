from pydantic import BaseModel


class ParsedCommand(BaseModel):
    action: str
    stock_symbol: str | None = None
    condition_type: str | None = None
    target_price: float | None = None
    target_percent: float | None = None
    target_multiplier: float | None = None
    ma_period: int | None = None
    window_minutes: int | None = None
    max_volume_lots: float | None = None
    active_weekdays: str | None = None
    monitor_start_time: str | None = None
    monitor_end_time: str | None = None
    raw_text: str
