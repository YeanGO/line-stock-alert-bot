from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.repositories.user_setting_repository import (
    set_morning_market_scan_enabled,
    set_morning_market_scan_schedule,
)
from app.repositories.watchlist_repository import create_morning_watchlist
from app.services.morning_scan_service import (
    MorningScanHit,
    _notify_morning_hit,
    evaluate_morning_symbol,
    is_morning_scan_window,
    is_schedule_active,
    merge_scan_symbols,
    normalize_market_symbol,
)


def test_normalize_market_symbol() -> None:
    assert normalize_market_symbol("2330") == "2330.TW"
    assert normalize_market_symbol("2330.TW") == "2330.TW"


def test_merge_scan_symbols_keeps_priority_first_and_unique() -> None:
    result = merge_scan_symbols(["2330.TW", "2317"], ["2317.TW", "2454.TW"])
    assert result == ["2330.TW", "2317.TW", "2454.TW"]


def test_schedule_active() -> None:
    now = datetime(2026, 6, 17, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))
    assert is_schedule_active("2,3,4", "09:30", "11:00", now) is True
    assert is_schedule_active("3,4", "09:30", "11:00", now) is False
    assert is_schedule_active("2,3,4", "10:30", "11:00", now) is False


def test_morning_scan_global_window_allows_weekday_morning() -> None:
    now = datetime(2026, 6, 17, 9, 30, tzinfo=ZoneInfo("Asia/Taipei"))
    assert is_morning_scan_window(now) is True


def test_evaluate_morning_symbol_hits_gain_and_low_volume() -> None:
    index = pd.date_range("2026-06-18 09:00", periods=21, freq="min", tz="Asia/Taipei")
    frame = pd.DataFrame(
        {"Close": [95.0] + [100.0] + [101.0] * 18 + [108.0], "Volume": [1000.0] + [90_000.0] * 20},
        index=index,
    )

    hit = evaluate_morning_symbol("2330.TW", frame, gain_threshold=0.08, volume_limit_lots=2500)

    assert hit is not None
    assert hit.symbol == "2330.TW"
    assert round(hit.gain_20m, 2) == 0.08
    assert hit.base_price == 100
    assert hit.volume_lots == 1800
    assert hit.window_minutes == 20


def test_evaluate_morning_symbol_uses_lowest_close_in_window() -> None:
    index = pd.date_range("2026-06-18 09:00", periods=21, freq="min", tz="Asia/Taipei")
    frame = pd.DataFrame(
        {"Close": [100.0] + [104.0] * 10 + [100.0] + [103.0] * 8 + [108.0], "Volume": [1000.0] + [90_000.0] * 20},
        index=index,
    )

    hit = evaluate_morning_symbol("2330.TW", frame, gain_threshold=0.08, volume_limit_lots=2500)

    assert hit is not None
    assert hit.base_price == 100
    assert round(hit.gain_20m, 2) == 0.08


def test_evaluate_morning_symbol_rejects_high_total_window_volume() -> None:
    index = pd.date_range("2026-06-18 09:00", periods=21, freq="min", tz="Asia/Taipei")
    frame = pd.DataFrame(
        {"Close": [100.0] + [101.0] * 19 + [108.0], "Volume": [1000.0] + [130_000.0] * 20},
        index=index,
    )

    assert evaluate_morning_symbol("2330.TW", frame, gain_threshold=0.08, volume_limit_lots=2500) is None


def test_notify_morning_hit_filters_by_watchlist_and_market_schedule(monkeypatch) -> None:
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    sent: list[tuple[str, str]] = []

    monkeypatch.setattr("app.services.morning_scan_service.push_text", lambda target_id, message: sent.append((target_id, message)))

    watchlist = create_morning_watchlist(
        db=session,
        line_user_id="U_WATCH",
        line_target_id="U_WATCH",
        target_type="user",
        stock_symbol="2330.TW",
        active_weekdays="2,3,4",
        monitor_start_time="09:30",
        monitor_end_time="11:00",
    )
    set_morning_market_scan_enabled(session, "U_MARKET", True)
    set_morning_market_scan_schedule(session, "U_MARKET", "09:30", "11:00", "2,3,4")
    set_morning_market_scan_enabled(session, "U_OUTSIDE", True)
    set_morning_market_scan_schedule(session, "U_OUTSIDE", "11:30", "12:00", "2,3,4")
    hit = MorningScanHit("2330.TW", price_now=108, base_price=100, gain_20m=0.08, volume_lots=1800)
    now = datetime(2026, 6, 17, 10, 0, tzinfo=ZoneInfo("Asia/Taipei"))

    stats = _notify_morning_hit(
        db=session,
        hit=hit,
        watchlists_by_symbol={"2330.TW": [watchlist]},
        market_scan_user_ids=["U_MARKET", "U_OUTSIDE"],
        alert_date="2026-06-17",
        alert_type="MORNING_GAIN_LOW_VOLUME",
        now=now,
    )

    assert stats["watchlist_notify_users"] == 1
    assert stats["market_scan_notify_users"] == 1
    assert stats["skipped_market_disabled"] == 1
    assert {target_id for target_id, _ in sent} == {"U_WATCH", "U_MARKET"}
    assert "來源：你的早盤監控清單" in sent[0][1]
    assert "來源：全市場掃描" in sent[1][1]

    duplicate_stats = _notify_morning_hit(
        db=session,
        hit=hit,
        watchlists_by_symbol={"2330.TW": [watchlist]},
        market_scan_user_ids=["U_MARKET"],
        alert_date="2026-06-17",
        alert_type="MORNING_GAIN_LOW_VOLUME",
        now=now,
    )
    assert duplicate_stats["skipped_duplicate"] == 2
