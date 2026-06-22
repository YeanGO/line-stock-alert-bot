from datetime import UTC, datetime

from app.models.watchlist import Watchlist
from app.schemas.stock import StockQuote
from app.services.rule_engine import evaluate_rule


def quote(**overrides) -> StockQuote:
    data = {
        "stock_symbol": "2330.TW",
        "current_price": 100.0,
        "previous_close": 95.0,
        "change_percent": 5.26,
        "current_volume": 2000.0,
        "avg_volume_5d": 1000.0,
        "ma5": 99.0,
        "ma10": 98.0,
        "ma20": 97.0,
        "ma60": 90.0,
        "previous_ma5": 99.0,
        "previous_ma10": 98.0,
        "previous_ma20": 97.0,
        "previous_ma60": 90.0,
        "updated_at": datetime.now(UTC),
    }
    data.update(overrides)
    return StockQuote(**data)


def watchlist(condition_type: str, **overrides) -> Watchlist:
    data = {
        "line_user_id": "U123",
        "stock_symbol": "2330.TW",
        "condition_type": condition_type,
        "cooldown_minutes": 30,
    }
    data.update(overrides)
    return Watchlist(**data)


def test_price_above_triggered() -> None:
    result = evaluate_rule(watchlist("price_above", target_price=90), quote())
    assert result.triggered is True


def test_price_below_triggered() -> None:
    result = evaluate_rule(watchlist("price_below", target_price=110), quote())
    assert result.triggered is True


def test_change_percent_above_triggered() -> None:
    result = evaluate_rule(watchlist("change_percent_above", target_percent=5), quote())
    assert result.triggered is True


def test_change_percent_below_triggered() -> None:
    result = evaluate_rule(watchlist("change_percent_below", target_percent=3), quote(change_percent=-4))
    assert result.triggered is True


def test_volume_spike_triggered() -> None:
    result = evaluate_rule(watchlist("volume_spike", target_multiplier=1.5), quote())
    assert result.triggered is True


def test_ma_breakout_triggered() -> None:
    result = evaluate_rule(watchlist("ma_breakout", ma_period=20), quote(previous_close=96, previous_ma20=97, ma20=99))
    assert result.triggered is True


def test_missing_target_does_not_trigger() -> None:
    result = evaluate_rule(watchlist("price_above"), quote())
    assert result.triggered is False


def test_removed_intraday_momentum_condition_is_unsupported() -> None:
    result = evaluate_rule(watchlist("intraday_momentum_volume_cap"), quote())
    assert result.triggered is False
    assert "unsupported condition_type" in result.reason
