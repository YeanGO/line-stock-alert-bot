import logging
from datetime import UTC, datetime, timedelta

import yfinance as yf

from app.config import get_settings
from app.schemas.stock import StockQuote

logger = logging.getLogger(__name__)


class StockQuoteFetchError(RuntimeError):
    pass


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    settings = get_settings()
    if "." not in value and value.isdigit():
        return f"{value}{settings.stock_symbol_suffix}"
    return value


def build_mock_quote(symbol: str) -> StockQuote:
    now = datetime.now(UTC)
    return StockQuote(
        stock_symbol=normalize_symbol(symbol),
        stock_name="Mock Stock",
        current_price=100.0,
        previous_close=98.0,
        change_percent=2.04,
        current_volume=1_500_000,
        avg_volume_5d=1_000_000,
        ma5=99.0,
        ma10=97.0,
        ma20=95.0,
        ma60=90.0,
        previous_ma5=98.5,
        previous_ma10=96.5,
        previous_ma20=94.5,
        previous_ma60=89.5,
        price_window_ago=92.0,
        intraday_change_percent=8.7,
        intraday_volume=2_000_000,
        updated_at=now,
    )


def get_intraday_momentum_quote(symbol: str, window_minutes: int, use_mock: bool = False) -> StockQuote:
    normalized_symbol = normalize_symbol(symbol)
    if use_mock:
        return build_mock_quote(normalized_symbol)

    try:
        ticker = yf.Ticker(normalized_symbol)
        history = ticker.history(period="1d", interval="1m", auto_adjust=False)
        if history.empty:
            raise StockQuoteFetchError(f"yfinance returned empty intraday history for {normalized_symbol}")

        close = history["Close"].dropna()
        volume = history["Volume"].fillna(0)
        if len(close) < 2:
            raise StockQuoteFetchError(f"not enough intraday history for {normalized_symbol}")

        current_price = float(close.iloc[-1])
        current_time = close.index[-1]
        target_time = current_time - timedelta(minutes=window_minutes)
        window_rows = close[close.index <= target_time]
        price_window_ago = float(window_rows.iloc[-1]) if len(window_rows) else float(close.iloc[0])
        intraday_change_percent = round(((current_price - price_window_ago) / price_window_ago) * 100, 2)

        return StockQuote(
            stock_symbol=normalized_symbol,
            stock_name=None,
            current_price=current_price,
            previous_close=price_window_ago,
            change_percent=intraday_change_percent,
            current_volume=float(volume.sum()),
            avg_volume_5d=None,
            price_window_ago=price_window_ago,
            intraday_change_percent=intraday_change_percent,
            intraday_volume=float(volume.sum()),
            updated_at=datetime.now(UTC),
        )
    except Exception as exc:
        logger.exception("Failed to fetch intraday yfinance quote for %s", normalized_symbol)
        raise StockQuoteFetchError(f"failed to fetch intraday quote for {normalized_symbol}") from exc


def get_stock_quote(symbol: str, use_mock: bool = False) -> StockQuote:
    normalized_symbol = normalize_symbol(symbol)
    if use_mock:
        return build_mock_quote(normalized_symbol)

    try:
        ticker = yf.Ticker(normalized_symbol)
        history = ticker.history(period="90d", interval="1d", auto_adjust=False)
        if history.empty:
            raise StockQuoteFetchError(f"yfinance returned empty daily history for {normalized_symbol}")

        close = history["Close"].dropna()
        volume = history["Volume"].dropna()
        current_price = float(close.iloc[-1])
        previous_close = float(close.iloc[-2]) if len(close) >= 2 else None
        change_percent = None
        if previous_close:
            change_percent = round(((current_price - previous_close) / previous_close) * 100, 2)

        def ma(period: int, offset: int = 0) -> float | None:
            series = close.rolling(period).mean().dropna()
            if len(series) <= offset:
                return None
            return float(series.iloc[-1 - offset])

        avg_volume_5d = float(volume.tail(5).mean()) if len(volume) >= 5 else None
        info = getattr(ticker, "fast_info", {}) or {}
        stock_name = None
        if isinstance(info, dict):
            stock_name = info.get("shortName") or info.get("longName")

        return StockQuote(
            stock_symbol=normalized_symbol,
            stock_name=stock_name,
            current_price=current_price,
            previous_close=previous_close,
            change_percent=change_percent,
            current_volume=float(volume.iloc[-1]) if len(volume) else None,
            avg_volume_5d=avg_volume_5d,
            ma5=ma(5),
            ma10=ma(10),
            ma20=ma(20),
            ma60=ma(60),
            previous_ma5=ma(5, 1),
            previous_ma10=ma(10, 1),
            previous_ma20=ma(20, 1),
            previous_ma60=ma(60, 1),
            updated_at=datetime.now(UTC),
        )
    except Exception as exc:
        logger.exception("Failed to fetch yfinance quote for %s", normalized_symbol)
        raise StockQuoteFetchError(f"failed to fetch daily quote for {normalized_symbol}") from exc
