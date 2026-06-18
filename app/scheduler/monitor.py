import logging
from collections import defaultdict
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.watchlist import Watchlist
from app.repositories.watchlist_repository import list_active_watchlists, update_condition_active
from app.services.alert_service import is_cooldown_elapsed, send_alert
from app.services.rule_engine import evaluate_rule
from app.services.stock_service import StockQuoteFetchError, get_intraday_momentum_quote, get_stock_quote

logger = logging.getLogger(__name__)
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
REGULAR_MARKET_START = time(9, 0)
REGULAR_MARKET_END = time(13, 30)


def is_taiwan_regular_market_open(now: datetime | None = None) -> bool:
    current = now or datetime.now(TAIPEI_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=TAIPEI_TZ)
    current = current.astimezone(TAIPEI_TZ)
    return current.weekday() < 5 and REGULAR_MARKET_START <= current.time() <= REGULAR_MARKET_END


def run_monitor(db: Session, use_mock_quotes: bool = False) -> dict[str, int]:
    watchlists = list_active_watchlists(db)
    grouped: dict[str, list[Watchlist]] = defaultdict(list)
    for watchlist in watchlists:
        grouped[watchlist.stock_symbol].append(watchlist)

    checked = 0
    triggered = 0
    skipped_cooldown = 0
    skipped_active = 0
    skipped_market_closed = 0
    skipped_quote_errors = 0

    for stock_symbol, stock_watchlists in grouped.items():
        for watchlist in stock_watchlists:
            checked += 1
            if watchlist.condition_type == "intraday_momentum_volume_cap":
                try:
                    quote = get_intraday_momentum_quote(
                        stock_symbol,
                        window_minutes=watchlist.window_minutes or 20,
                        use_mock=use_mock_quotes,
                    )
                except StockQuoteFetchError:
                    skipped_quote_errors += 1
                    continue
            else:
                if not is_taiwan_regular_market_open():
                    skipped_market_closed += 1
                    continue
                try:
                    quote = get_stock_quote(stock_symbol, use_mock=use_mock_quotes)
                except StockQuoteFetchError:
                    skipped_quote_errors += 1
                    continue

            evaluation = evaluate_rule(watchlist, quote)
            if not evaluation.triggered:
                if watchlist.condition_type == "intraday_momentum_volume_cap" and watchlist.is_condition_active:
                    update_condition_active(db, watchlist, False)
                continue
            if watchlist.condition_type == "intraday_momentum_volume_cap" and watchlist.is_condition_active:
                skipped_active += 1
                continue
            if not is_cooldown_elapsed(watchlist):
                skipped_cooldown += 1
                continue
            send_alert(db, watchlist, quote, evaluation.reason)
            if watchlist.condition_type == "intraday_momentum_volume_cap":
                update_condition_active(db, watchlist, True)
            triggered += 1

    result = {
        "checked": checked,
        "triggered": triggered,
        "skipped_cooldown": skipped_cooldown,
        "skipped_active": skipped_active,
        "skipped_market_closed": skipped_market_closed,
        "skipped_quote_errors": skipped_quote_errors,
    }
    logger.info("Monitor completed: %s", result)
    return result
