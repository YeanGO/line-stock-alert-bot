import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yfinance as yf
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models.watchlist import Watchlist
from app.repositories.alert_history_repository import create_morning_alert_history, has_morning_alert_sent
from app.repositories.user_setting_repository import (
    get_morning_market_scan_conditions,
    get_morning_market_scan_schedule,
    list_morning_market_scan_enabled_target_ids,
)
from app.repositories.watchlist_repository import get_or_create_morning_market_watchlist, list_active_morning_watchlists
from app.services.line_service import push_text

logger = logging.getLogger(__name__)
TAIPEI_TZ = ZoneInfo("Asia/Taipei")
scan_lock = threading.Lock()


@dataclass
class MorningScanHit:
    symbol: str
    price_now: float
    base_price: float
    gain_20m: float
    volume_lots: float
    window_minutes: int = 20
    gain_threshold: float = 0.08
    volume_limit_lots: float = 2500.0


@dataclass
class MorningNotifyCandidate:
    target_id: str
    source_label: str
    title: str
    source_type: str
    window_minutes: int
    gain_percent: float
    volume_limit_lots: float
    watchlist: Watchlist | None = None


def normalize_market_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if not value:
        return ""
    if "." not in value and value.isdigit():
        return f"{value}.TW"
    return value


def load_market_symbols(path: str = "data/twse_listed_symbols.txt") -> list[str]:
    symbol_path = Path(path)
    if not symbol_path.exists():
        logger.warning("market symbol file not found: %s", symbol_path)
        return []

    symbols: list[str] = []
    for line in symbol_path.read_text(encoding="utf-8").splitlines():
        symbol = normalize_market_symbol(line)
        if symbol and not symbol.startswith("#"):
            symbols.append(symbol)
    return list(dict.fromkeys(symbols))


def merge_scan_symbols(priority_symbols: list[str], market_symbols: list[str]) -> list[str]:
    ordered = [normalize_market_symbol(symbol) for symbol in priority_symbols + market_symbols]
    return [symbol for symbol in dict.fromkeys(ordered) if symbol]


def is_schedule_active(weekdays: str | None, start_time: str | None, end_time: str | None, now: datetime | None = None) -> bool:
    current = now or datetime.now(TAIPEI_TZ)
    if current.tzinfo is None:
        current = current.replace(tzinfo=TAIPEI_TZ)
    current = current.astimezone(TAIPEI_TZ)

    active_weekdays = {int(value) for value in (weekdays or "3,4").split(",") if value.strip()}
    if current.weekday() not in active_weekdays:
        return False
    hhmm = current.strftime("%H:%M")
    return (start_time or "09:00") <= hhmm <= (end_time or "10:30")


def is_morning_scan_window(now: datetime | None = None) -> bool:
    settings = get_settings()
    return is_schedule_active(
        settings.morning_scan_weekdays,
        settings.morning_scan_start,
        settings.morning_scan_end,
        now=now,
    )


def _extract_symbol_frame(downloaded: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if downloaded.empty:
        return pd.DataFrame()
    if isinstance(downloaded.columns, pd.MultiIndex):
        if symbol in downloaded.columns.get_level_values(0):
            return downloaded[symbol]
        return pd.DataFrame()
    return downloaded


def evaluate_morning_symbol(
    symbol: str,
    frame: pd.DataFrame,
    gain_threshold: float,
    volume_limit_lots: float,
    window_minutes: int = 20,
) -> MorningScanHit | None:
    if frame.empty or "Close" not in frame or "Volume" not in frame:
        return None

    close = frame["Close"].dropna()
    volume = frame["Volume"].dropna()
    valid_index = close.index.intersection(volume.index)
    close = close.loc[valid_index]
    volume = volume.loc[valid_index]
    if len(close) < 2:
        return None

    price_now = float(close.iloc[-1])
    close_window = close.tail(window_minutes)
    base_price = float(close_window.min())
    volume_window = float(volume.loc[close_window.index].sum())
    if base_price <= 0 or pd.isna(price_now) or pd.isna(volume_window):
        return None

    gain_20m = (price_now - base_price) / base_price
    volume_lots = volume_window / 1000
    if gain_20m >= gain_threshold and volume_lots <= volume_limit_lots:
        return MorningScanHit(
            symbol=symbol,
            price_now=price_now,
            base_price=base_price,
            gain_20m=gain_20m,
            volume_lots=volume_lots,
            window_minutes=window_minutes,
            gain_threshold=gain_threshold,
            volume_limit_lots=volume_limit_lots,
        )
    return None


def download_morning_batch(symbols: list[str]) -> pd.DataFrame:
    return yf.download(
        tickers=symbols,
        period="1d",
        interval="1m",
        group_by="ticker",
        threads=True,
        progress=False,
    )


def _build_morning_message(hit: MorningScanHit, source_label: str, title: str) -> str:
    return (
        f"{title}\n\n"
        f"來源：{source_label}\n"
        f"股票：{hit.symbol.replace('.TW', '')}\n"
        f"{hit.window_minutes}分鐘內最大漲幅：{hit.gain_20m * 100:.2f}%\n"
        f"{hit.window_minutes}分鐘總成交量：{hit.volume_lots:.0f} 張\n"
        f"目前價格：{hit.price_now}\n"
        f"基準價格：{hit.base_price}\n\n"
        f"條件：{hit.window_minutes}分鐘內任一分鐘到現在漲幅 >= {hit.gain_threshold * 100:g}%，"
        f"總成交量 <= {hit.volume_limit_lots:g}張"
    )


def _build_morning_candidates(
    db: Session,
    symbol: str,
    watchlists_by_symbol: dict[str, list[Watchlist]],
    market_scan_target_ids: list[str],
    now: datetime | None = None,
) -> tuple[dict[str, MorningNotifyCandidate], int]:
    candidates: dict[str, MorningNotifyCandidate] = {}
    skipped_market_disabled = 0

    for watchlist in watchlists_by_symbol.get(symbol, []):
        if not is_schedule_active(
            watchlist.active_weekdays,
            watchlist.monitor_start_time,
            watchlist.monitor_end_time,
            now=now,
        ):
            continue
        target_id = watchlist.line_target_id or watchlist.line_user_id
        candidates[target_id] = MorningNotifyCandidate(
            target_id=target_id,
            source_label="你的早盤監控清單",
            title="早盤監控觸發",
            source_type="watchlist",
            window_minutes=watchlist.window_minutes or 20,
            gain_percent=watchlist.target_percent or 8.0,
            volume_limit_lots=watchlist.max_volume_lots or 2500.0,
            watchlist=watchlist,
        )

    for target_id in market_scan_target_ids:
        start_time, end_time, weekdays = get_morning_market_scan_schedule(db, target_id)
        if not start_time or not end_time or not weekdays:
            skipped_market_disabled += 1
            continue
        if not is_schedule_active(weekdays, start_time, end_time, now=now):
            skipped_market_disabled += 1
            continue
        if target_id in candidates:
            continue
        window_minutes, gain_percent, volume_limit_lots = get_morning_market_scan_conditions(db, target_id)
        if window_minutes is None or gain_percent is None or volume_limit_lots is None:
            skipped_market_disabled += 1
            continue
        candidates[target_id] = MorningNotifyCandidate(
            target_id=target_id,
            source_label="全市場掃描",
            title="早盤全市場訊號",
            source_type="market",
            window_minutes=window_minutes,
            gain_percent=gain_percent,
            volume_limit_lots=volume_limit_lots,
        )

    return candidates, skipped_market_disabled


def _notify_morning_candidate(
    db: Session,
    hit: MorningScanHit,
    candidate: MorningNotifyCandidate,
    watchlists_by_symbol: dict[str, list[Watchlist]],
    alert_date: str,
    alert_type: str,
) -> dict[str, int]:
    stats = {
        "watchlist_notify_users": 0,
        "market_scan_notify_users": 0,
        "skipped_duplicate": 0,
        "line_success": 0,
        "line_failed": 0,
    }

    if has_morning_alert_sent(db, candidate.target_id, hit.symbol, alert_date, alert_type):
        stats["skipped_duplicate"] += 1
        return stats

    history_watchlist = candidate.watchlist or _history_watchlist_for_target(
        hit.symbol,
        candidate.target_id,
        watchlists_by_symbol,
        None,
    )
    if history_watchlist is None:
        history_watchlist = get_or_create_morning_market_watchlist(db, candidate.target_id, alert_type)

    message = _build_morning_message(hit, source_label=candidate.source_label, title=candidate.title)
    try:
        push_text(candidate.target_id, message)
        stats["line_success"] += 1
    except Exception:
        logger.exception("failed to push morning alert target=%s symbol=%s", candidate.target_id, hit.symbol)
        stats["line_failed"] += 1
        return stats

    create_morning_alert_history(
        db=db,
        watchlist=history_watchlist,
        message=message,
        alert_date=alert_date,
        price_now=hit.price_now,
        price_20m_ago=hit.base_price,
        gain_20m=hit.gain_20m,
        volume_lots=hit.volume_lots,
        alert_type=alert_type,
        line_target_id=candidate.target_id,
        stock_symbol=hit.symbol,
    )
    if candidate.source_type == "watchlist":
        stats["watchlist_notify_users"] += 1
    else:
        stats["market_scan_notify_users"] += 1

    return stats


def _history_watchlist_for_target(
    symbol: str,
    target_id: str,
    watchlists_by_symbol: dict[str, list[Watchlist]],
    fallback_watchlist: Watchlist | None,
) -> Watchlist | None:
    for watchlist in watchlists_by_symbol.get(symbol, []):
        if (watchlist.line_target_id or watchlist.line_user_id) == target_id:
            return watchlist
    return fallback_watchlist


def _notify_morning_hit(
    db: Session,
    hit: MorningScanHit,
    watchlists_by_symbol: dict[str, list[Watchlist]],
    market_scan_user_ids: list[str],
    alert_date: str,
    alert_type: str,
    now: datetime | None = None,
) -> dict[str, int]:
    stats = {
        "watchlist_notify_users": 0,
        "market_scan_notify_users": 0,
        "skipped_duplicate": 0,
        "skipped_market_disabled": 0,
        "line_success": 0,
        "line_failed": 0,
    }

    symbol_watchlists = watchlists_by_symbol.get(hit.symbol, [])
    fallback_watchlist = symbol_watchlists[0] if symbol_watchlists else None
    candidates: dict[str, tuple[str, str, str]] = {}

    for watchlist in symbol_watchlists:
        if not is_schedule_active(
            watchlist.active_weekdays,
            watchlist.monitor_start_time,
            watchlist.monitor_end_time,
            now=now,
        ):
            continue
        target_id = watchlist.line_target_id or watchlist.line_user_id
        candidates[target_id] = ("你的早盤監控清單", "早盤監控觸發", "watchlist")

    for user_id in market_scan_user_ids:
        start_time, end_time, weekdays = get_morning_market_scan_schedule(db, user_id)
        if not start_time or not end_time or not weekdays:
            stats["skipped_market_disabled"] += 1
            continue
        if not is_schedule_active(weekdays, start_time, end_time, now=now):
            stats["skipped_market_disabled"] += 1
            continue
        if user_id not in candidates:
            candidates[user_id] = ("全市場掃描", "早盤全市場訊號", "market")

    if not market_scan_user_ids and not symbol_watchlists:
        stats["skipped_market_disabled"] += 1

    for target_id, (source_label, title, source_type) in candidates.items():
        if has_morning_alert_sent(db, target_id, hit.symbol, alert_date, alert_type):
            stats["skipped_duplicate"] += 1
            continue

        history_watchlist = _history_watchlist_for_target(hit.symbol, target_id, watchlists_by_symbol, fallback_watchlist)
        if history_watchlist is None:
            history_watchlist = get_or_create_morning_market_watchlist(db, target_id, alert_type)

        message = _build_morning_message(hit, source_label=source_label, title=title)
        try:
            push_text(target_id, message)
            stats["line_success"] += 1
        except Exception:
            logger.exception("failed to push morning alert target=%s symbol=%s", target_id, hit.symbol)
            stats["line_failed"] += 1
            continue

        create_morning_alert_history(
            db=db,
            watchlist=history_watchlist,
            message=message,
            alert_date=alert_date,
        price_now=hit.price_now,
        price_20m_ago=hit.base_price,
            gain_20m=hit.gain_20m,
            volume_lots=hit.volume_lots,
            alert_type=alert_type,
            line_target_id=target_id,
            stock_symbol=hit.symbol,
        )
        if source_type == "watchlist":
            stats["watchlist_notify_users"] += 1
        else:
            stats["market_scan_notify_users"] += 1

    return stats


def run_morning_gain_low_volume_scan(db: Session) -> dict[str, int | float | bool]:
    settings = get_settings()
    started = time.perf_counter()
    if not scan_lock.acquire(blocking=False):
        logger.warning("morning scan skipped because previous scan is still running")
        return {"locked": True, "scanned": 0, "triggered": 0}

    try:
        now = datetime.now(TAIPEI_TZ)
        if not is_morning_scan_window(now):
            logger.info("morning scan skipped outside scan window")
            return {"locked": False, "scanned": 0, "triggered": 0}

        watchlists = list_active_morning_watchlists(db, settings.morning_alert_type)
        priority_symbols = [watchlist.stock_symbol for watchlist in watchlists]
        final_symbols = merge_scan_symbols(priority_symbols, load_market_symbols())
        if not final_symbols:
            logger.warning("morning scan has no symbols to scan")
            return {"locked": False, "scanned": 0, "triggered": 0}

        watchlists_by_symbol: dict[str, list[Watchlist]] = defaultdict(list)
        for watchlist in watchlists:
            watchlists_by_symbol[watchlist.stock_symbol].append(watchlist)
        market_scan_user_ids = list_morning_market_scan_enabled_target_ids(db)

        alert_date = now.strftime("%Y-%m-%d")
        counters = defaultdict(int)

        for batch_start in range(0, len(final_symbols), settings.batch_size):
            elapsed = time.perf_counter() - started
            if elapsed >= settings.max_scan_seconds:
                logger.warning("morning scan reached max runtime %.2fs and stopped early", elapsed)
                break

            batch = final_symbols[batch_start : batch_start + settings.batch_size]
            try:
                downloaded = download_morning_batch(batch)
            except Exception:
                counters["failed_batches"] += 1
                logger.exception("morning scan failed batch starting at %s", batch_start)
                time.sleep(1)
                continue

            for symbol in batch:
                counters["scanned"] += 1
                frame = _extract_symbol_frame(downloaded, symbol)
                candidates, skipped_market_disabled = _build_morning_candidates(
                    db=db,
                    symbol=symbol,
                    watchlists_by_symbol=watchlists_by_symbol,
                    market_scan_target_ids=market_scan_user_ids,
                    now=now,
                )
                counters["skipped_market_disabled"] += skipped_market_disabled
                if not candidates:
                    continue

                hit_targets: set[str] = set()
                symbol_market_hit = False
                symbol_watchlist_hit = False
                hit_cache: dict[tuple[int, float, float], MorningScanHit | None] = {}

                for candidate in candidates.values():
                    rule_key = (
                        candidate.window_minutes,
                        candidate.gain_percent,
                        candidate.volume_limit_lots,
                    )
                    if rule_key not in hit_cache:
                        hit_cache[rule_key] = evaluate_morning_symbol(
                            symbol=symbol,
                            frame=frame,
                            gain_threshold=candidate.gain_percent / 100,
                            volume_limit_lots=candidate.volume_limit_lots,
                            window_minutes=candidate.window_minutes,
                        )
                    hit = hit_cache[rule_key]
                    if hit is None:
                        continue

                    symbol_market_hit = True
                    if candidate.source_type == "watchlist":
                        symbol_watchlist_hit = True

                    notify_stats = _notify_morning_candidate(
                        db=db,
                        hit=hit,
                        candidate=candidate,
                        watchlists_by_symbol=watchlists_by_symbol,
                        alert_date=alert_date,
                        alert_type=settings.morning_alert_type,
                    )
                    for key, value in notify_stats.items():
                        counters[key] += value
                    if notify_stats["watchlist_notify_users"] or notify_stats["market_scan_notify_users"]:
                        hit_targets.add(candidate.target_id)

                if symbol_market_hit:
                    counters["market_hit_symbols"] += 1
                if symbol_watchlist_hit:
                    counters["watchlist_hit_symbols"] += 1
                counters["triggered"] += len(hit_targets)

        elapsed = time.perf_counter() - started
        logger.info(
            (
                "morning scan finished scanned=%s market_hits=%s watchlist_hits=%s "
                "market_notify_users=%s watchlist_notify_users=%s duplicates=%s market_disabled=%s "
                "line_success=%s line_failed=%s failed_batches=%s elapsed=%.2fs"
            ),
            counters["scanned"],
            counters["market_hit_symbols"],
            counters["watchlist_hit_symbols"],
            counters["market_scan_notify_users"],
            counters["watchlist_notify_users"],
            counters["skipped_duplicate"],
            counters["skipped_market_disabled"],
            counters["line_success"],
            counters["line_failed"],
            counters["failed_batches"],
            elapsed,
        )
        return {
            "locked": False,
            "scanned": counters["scanned"],
            "triggered": counters["triggered"],
            "market_hit_symbols": counters["market_hit_symbols"],
            "watchlist_hit_symbols": counters["watchlist_hit_symbols"],
            "market_scan_notify_users": counters["market_scan_notify_users"],
            "watchlist_notify_users": counters["watchlist_notify_users"],
            "failed_batches": counters["failed_batches"],
            "skipped_duplicate": counters["skipped_duplicate"],
            "skipped_market_disabled": counters["skipped_market_disabled"],
            "line_success": counters["line_success"],
            "line_failed": counters["line_failed"],
            "elapsed": elapsed,
        }
    finally:
        scan_lock.release()
