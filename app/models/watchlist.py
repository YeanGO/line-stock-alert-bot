from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.datetime_utils import utc_now


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    line_user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    line_target_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    target_type: Mapped[str] = mapped_column(String(16), default="user", nullable=False)
    created_by_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    rule_type: Mapped[str] = mapped_column(String(64), default="PRICE_ALERT", nullable=False)
    stock_symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    stock_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    condition_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    target_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    ma_period: Mapped[int | None] = mapped_column(Integer, nullable=True)
    window_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_volume_lots: Mapped[float | None] = mapped_column(Float, nullable=True)
    active_weekdays: Mapped[str | None] = mapped_column(String(32), nullable=True)
    monitor_start_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    monitor_end_time: Mapped[str | None] = mapped_column(String(8), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_condition_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cooldown_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    last_triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
