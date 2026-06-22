from datetime import datetime

from pydantic import BaseModel


class StockQuote(BaseModel):
    stock_symbol: str
    stock_name: str | None = None
    current_price: float
    previous_close: float | None = None
    change_percent: float | None = None
    current_volume: float | None = None
    avg_volume_5d: float | None = None
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    ma60: float | None = None
    previous_ma5: float | None = None
    previous_ma10: float | None = None
    previous_ma20: float | None = None
    previous_ma60: float | None = None
    updated_at: datetime
