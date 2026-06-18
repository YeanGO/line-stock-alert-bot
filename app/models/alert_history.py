from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.utils.datetime_utils import utc_now


class AlertHistory(Base):
    __tablename__ = "alert_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id"), nullable=False)
    line_user_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    line_target_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    stock_symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    condition_type: Mapped[str] = mapped_column(String(64), nullable=False)
    alert_type: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    alert_date: Mapped[str | None] = mapped_column(String(10), index=True, nullable=True)
    current_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_20m_ago: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    gain_20m: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_volume: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_lots: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
