from sqlalchemy.orm import Session

from app.models.alert_history import AlertHistory
from app.models.watchlist import Watchlist
from app.schemas.stock import StockQuote


def create_alert_history(db: Session, watchlist: Watchlist, quote: StockQuote, message: str) -> AlertHistory:
    alert = AlertHistory(
        watchlist_id=watchlist.id,
        line_user_id=watchlist.line_user_id,
        line_target_id=watchlist.line_target_id or watchlist.line_user_id,
        stock_symbol=watchlist.stock_symbol,
        condition_type=watchlist.condition_type,
        current_price=quote.current_price,
        change_percent=quote.change_percent,
        current_volume=quote.current_volume,
        message=message,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def has_morning_alert_sent(
    db: Session,
    line_target_id: str,
    stock_symbol: str,
    alert_date: str,
    alert_type: str = "MORNING_GAIN_LOW_VOLUME",
) -> bool:
    return (
        db.query(AlertHistory)
        .filter(
            AlertHistory.line_target_id == line_target_id,
            AlertHistory.stock_symbol == stock_symbol,
            AlertHistory.alert_date == alert_date,
            AlertHistory.alert_type == alert_type,
        )
        .first()
        is not None
    )


def create_morning_alert_history(
    db: Session,
    watchlist: Watchlist,
    message: str,
    alert_date: str,
    price_now: float,
    price_20m_ago: float,
    gain_20m: float,
    volume_lots: float,
    alert_type: str = "MORNING_GAIN_LOW_VOLUME",
    line_target_id: str | None = None,
    stock_symbol: str | None = None,
) -> AlertHistory:
    alert = AlertHistory(
        watchlist_id=watchlist.id,
        line_user_id=watchlist.line_user_id,
        line_target_id=line_target_id or watchlist.line_target_id or watchlist.line_user_id,
        stock_symbol=stock_symbol or watchlist.stock_symbol,
        condition_type=watchlist.condition_type,
        alert_type=alert_type,
        alert_date=alert_date,
        current_price=price_now,
        price_20m_ago=price_20m_ago,
        change_percent=round(gain_20m * 100, 2),
        gain_20m=gain_20m,
        current_volume=volume_lots * 1000,
        volume_lots=volume_lots,
        message=message,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
