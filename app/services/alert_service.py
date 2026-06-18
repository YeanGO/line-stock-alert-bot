from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.models.watchlist import Watchlist
from app.repositories.alert_history_repository import create_alert_history
from app.repositories.watchlist_repository import update_last_triggered_at
from app.schemas.stock import StockQuote
from app.services.line_service import push_text


def is_cooldown_elapsed(watchlist: Watchlist, now: datetime | None = None) -> bool:
    if watchlist.last_triggered_at is None:
        return True
    current_time = now or datetime.now(UTC)
    last_triggered_at = watchlist.last_triggered_at
    if last_triggered_at.tzinfo is None:
        last_triggered_at = last_triggered_at.replace(tzinfo=UTC)
    return current_time - last_triggered_at >= timedelta(minutes=watchlist.cooldown_minutes)


def build_alert_message(watchlist: Watchlist, quote: StockQuote, reason: str) -> str:
    change = "" if quote.change_percent is None else f" ({quote.change_percent:+.2f}%)"
    return (
        f"{watchlist.stock_symbol} alert triggered\n"
        f"Price: {quote.current_price}{change}\n"
        f"Condition: {watchlist.condition_type}\n"
        f"Reason: {reason}"
    )


def send_alert(db: Session, watchlist: Watchlist, quote: StockQuote, reason: str) -> str:
    message = build_alert_message(watchlist, quote, reason)
    push_text(watchlist.line_target_id or watchlist.line_user_id, message)
    create_alert_history(db, watchlist, quote, message)
    update_last_triggered_at(db, watchlist, datetime.now(UTC))
    return message
