from datetime import datetime
from zoneinfo import ZoneInfo

from app.scheduler.monitor import is_taiwan_regular_market_open


def test_taiwan_regular_market_open_during_weekday_session() -> None:
    now = datetime(2026, 6, 18, 9, 30, tzinfo=ZoneInfo("Asia/Taipei"))
    assert is_taiwan_regular_market_open(now) is True


def test_taiwan_regular_market_closed_before_open() -> None:
    now = datetime(2026, 6, 18, 8, 59, tzinfo=ZoneInfo("Asia/Taipei"))
    assert is_taiwan_regular_market_open(now) is False


def test_taiwan_regular_market_closed_after_close() -> None:
    now = datetime(2026, 6, 18, 13, 31, tzinfo=ZoneInfo("Asia/Taipei"))
    assert is_taiwan_regular_market_open(now) is False


def test_taiwan_regular_market_closed_on_weekend() -> None:
    now = datetime(2026, 6, 20, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert is_taiwan_regular_market_open(now) is False
