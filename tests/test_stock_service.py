from app.schemas.stock import StockQuote
import pandas as pd
import pytest

from app.services.stock_service import (
    StockQuoteFetchError,
    build_mock_quote,
    get_stock_quote,
    normalize_symbol,
)


def test_normalize_tw_stock_symbol() -> None:
    assert normalize_symbol("2330") == "2330.TW"


def test_mock_quote_returns_stock_quote() -> None:
    quote = build_mock_quote("2330")
    assert isinstance(quote, StockQuote)
    assert quote.stock_symbol == "2330.TW"
    assert quote.current_price > 0


def test_get_stock_quote_can_use_mock_without_yfinance_network() -> None:
    quote = get_stock_quote("2330", use_mock=True)
    assert isinstance(quote, StockQuote)
    assert quote.stock_symbol == "2330.TW"


def test_get_stock_quote_does_not_fallback_to_mock_on_empty_yfinance(monkeypatch: pytest.MonkeyPatch) -> None:
    class EmptyTicker:
        def __init__(self, symbol: str) -> None:
            self.symbol = symbol

        def history(self, *args, **kwargs) -> pd.DataFrame:
            return pd.DataFrame()

    monkeypatch.setattr("app.services.stock_service.yf.Ticker", EmptyTicker)

    with pytest.raises(StockQuoteFetchError):
        get_stock_quote("2330")
