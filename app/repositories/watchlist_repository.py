from datetime import datetime

from sqlalchemy.orm import Session

from app.models.watchlist import Watchlist
from app.schemas.command import ParsedCommand


def create_watchlist_from_command(
    db: Session,
    line_user_id: str,
    command: ParsedCommand,
    cooldown_minutes: int,
    line_target_id: str | None = None,
    target_type: str = "user",
    created_by_user_id: str | None = None,
    rule_type: str = "PRICE_ALERT",
) -> Watchlist:
    target_id = line_target_id or line_user_id
    watchlist = Watchlist(
        line_user_id=line_user_id,
        line_target_id=target_id,
        target_type=target_type,
        created_by_user_id=created_by_user_id or line_user_id,
        rule_type=rule_type,
        stock_symbol=command.stock_symbol or "",
        condition_type=command.condition_type or "",
        target_price=command.target_price,
        target_percent=command.target_percent,
        target_multiplier=command.target_multiplier,
        ma_period=command.ma_period,
        window_minutes=command.window_minutes,
        max_volume_lots=command.max_volume_lots,
        active_weekdays=command.active_weekdays,
        monitor_start_time=command.monitor_start_time,
        monitor_end_time=command.monitor_end_time,
        cooldown_minutes=cooldown_minutes,
    )
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return watchlist


def get_morning_watchlist(
    db: Session,
    line_target_id: str,
    stock_symbol: str,
    rule_type: str = "MORNING_GAIN_LOW_VOLUME",
) -> Watchlist | None:
    return (
        db.query(Watchlist)
        .filter(
            Watchlist.is_active.is_(True),
            Watchlist.rule_type == rule_type,
            Watchlist.stock_symbol == stock_symbol,
            (Watchlist.line_target_id == line_target_id) | (Watchlist.line_user_id == line_target_id),
        )
        .one_or_none()
    )


def create_morning_watchlist(
    db: Session,
    line_user_id: str,
    line_target_id: str,
    target_type: str,
    stock_symbol: str,
    created_by_user_id: str | None = None,
    rule_type: str = "MORNING_GAIN_LOW_VOLUME",
    active_weekdays: str = "3,4",
    monitor_start_time: str = "09:00",
    monitor_end_time: str = "10:30",
    window_minutes: int = 20,
    target_percent: float = 8.0,
    max_volume_lots: float = 2500.0,
) -> Watchlist:
    watchlist = Watchlist(
        line_user_id=line_user_id,
        line_target_id=line_target_id,
        target_type=target_type,
        created_by_user_id=created_by_user_id or line_user_id,
        rule_type=rule_type,
        stock_symbol=stock_symbol,
        condition_type=rule_type,
        target_percent=target_percent,
        max_volume_lots=max_volume_lots,
        window_minutes=window_minutes,
        active_weekdays=active_weekdays,
        monitor_start_time=monitor_start_time,
        monitor_end_time=monitor_end_time,
        cooldown_minutes=0,
    )
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return watchlist


def get_or_create_morning_market_watchlist(
    db: Session,
    line_user_id: str,
    rule_type: str = "MORNING_GAIN_LOW_VOLUME",
) -> Watchlist:
    stock_symbol = "__MARKET__"
    watchlist = (
        db.query(Watchlist)
        .filter(
            Watchlist.rule_type == rule_type,
            Watchlist.stock_symbol == stock_symbol,
            Watchlist.line_target_id == line_user_id,
        )
        .one_or_none()
    )
    if watchlist is not None:
        if not watchlist.is_active:
            watchlist.is_active = True
            db.commit()
            db.refresh(watchlist)
        return watchlist

    watchlist = Watchlist(
        line_user_id=line_user_id,
        line_target_id=line_user_id,
        target_type="user",
        created_by_user_id=line_user_id,
        rule_type=rule_type,
        stock_symbol=stock_symbol,
        condition_type=rule_type,
        target_percent=8.0,
        max_volume_lots=2500.0,
        window_minutes=20,
        active_weekdays="3,4",
        monitor_start_time="09:00",
        monitor_end_time="10:30",
        cooldown_minutes=0,
    )
    db.add(watchlist)
    db.commit()
    db.refresh(watchlist)
    return watchlist


def list_morning_watchlists(db: Session, line_target_id: str, rule_type: str = "MORNING_GAIN_LOW_VOLUME") -> list[Watchlist]:
    return (
        db.query(Watchlist)
        .filter(
            Watchlist.is_active.is_(True),
            Watchlist.rule_type == rule_type,
            Watchlist.stock_symbol != "__MARKET__",
            (Watchlist.line_target_id == line_target_id) | (Watchlist.line_user_id == line_target_id),
        )
        .order_by(Watchlist.stock_symbol.asc())
        .all()
    )


def list_active_morning_watchlists(db: Session, rule_type: str = "MORNING_GAIN_LOW_VOLUME") -> list[Watchlist]:
    return (
        db.query(Watchlist)
        .filter(
            Watchlist.is_active.is_(True),
            Watchlist.rule_type == rule_type,
            Watchlist.stock_symbol != "__MARKET__",
        )
        .all()
    )


def deactivate_morning_watchlist(
    db: Session,
    line_target_id: str,
    stock_symbol: str,
    rule_type: str = "MORNING_GAIN_LOW_VOLUME",
) -> int:
    rows = (
        db.query(Watchlist)
        .filter(
            Watchlist.is_active.is_(True),
            Watchlist.rule_type == rule_type,
            Watchlist.stock_symbol == stock_symbol,
            (Watchlist.line_target_id == line_target_id) | (Watchlist.line_user_id == line_target_id),
        )
        .all()
    )
    for row in rows:
        row.is_active = False
    db.commit()
    return len(rows)


def list_target_watchlists(db: Session, line_target_id: str) -> list[Watchlist]:
    return (
        db.query(Watchlist)
        .filter(
            Watchlist.is_active.is_(True),
            (Watchlist.line_target_id == line_target_id) | (Watchlist.line_user_id == line_target_id),
        )
        .order_by(Watchlist.created_at.desc())
        .all()
    )


def list_user_watchlists(db: Session, line_user_id: str) -> list[Watchlist]:
    return list_target_watchlists(db, line_user_id)


def list_active_watchlists(db: Session) -> list[Watchlist]:
    return db.query(Watchlist).filter(Watchlist.is_active.is_(True)).all()


def deactivate_target_stock_watchlists(db: Session, line_target_id: str, stock_symbol: str) -> int:
    rows = (
        db.query(Watchlist)
        .filter(
            (Watchlist.line_target_id == line_target_id) | (Watchlist.line_user_id == line_target_id),
            Watchlist.stock_symbol == stock_symbol,
            Watchlist.is_active.is_(True),
        )
        .all()
    )
    for row in rows:
        row.is_active = False
    db.commit()
    return len(rows)


def deactivate_stock_watchlists(db: Session, line_user_id: str, stock_symbol: str) -> int:
    return deactivate_target_stock_watchlists(db, line_user_id, stock_symbol)


def update_last_triggered_at(db: Session, watchlist: Watchlist, triggered_at: datetime) -> Watchlist:
    watchlist.last_triggered_at = triggered_at
    db.commit()
    db.refresh(watchlist)
    return watchlist


def update_condition_active(db: Session, watchlist: Watchlist, is_active: bool) -> Watchlist:
    watchlist.is_condition_active = is_active
    db.commit()
    db.refresh(watchlist)
    return watchlist
