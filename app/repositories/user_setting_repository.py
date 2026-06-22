from sqlalchemy.orm import Session

from app.models.user_setting import UserSetting
from app.repositories.watchlist_repository import get_or_create_morning_market_watchlist

MORNING_MARKET_SCAN_ENABLED = "MORNING_MARKET_SCAN_ENABLED"
MORNING_MARKET_SCAN_START = "MORNING_MARKET_SCAN_START"
MORNING_MARKET_SCAN_END = "MORNING_MARKET_SCAN_END"
MORNING_MARKET_SCAN_WEEKDAYS = "MORNING_MARKET_SCAN_WEEKDAYS"
MORNING_MARKET_SCAN_WINDOW_MINUTES = "MORNING_MARKET_SCAN_WINDOW_MINUTES"
MORNING_MARKET_SCAN_GAIN_PERCENT = "MORNING_MARKET_SCAN_GAIN_PERCENT"
MORNING_MARKET_SCAN_VOLUME_LIMIT_LOTS = "MORNING_MARKET_SCAN_VOLUME_LIMIT_LOTS"


def get_setting(db: Session, owner_id: str, setting_key: str) -> UserSetting | None:
    return (
        db.query(UserSetting)
        .filter(UserSetting.user_id == owner_id, UserSetting.setting_key == setting_key)
        .one_or_none()
    )


def set_setting(db: Session, owner_id: str, setting_key: str, setting_value: str) -> UserSetting:
    setting = get_setting(db, owner_id, setting_key)
    if setting is None:
        setting = UserSetting(user_id=owner_id, setting_key=setting_key, setting_value=setting_value)
        db.add(setting)
    else:
        setting.setting_value = setting_value
    db.commit()
    db.refresh(setting)
    return setting


def is_morning_market_scan_enabled(db: Session, owner_id: str) -> bool:
    setting = get_setting(db, owner_id, MORNING_MARKET_SCAN_ENABLED)
    return setting is not None and setting.setting_value.lower() == "true"


def set_morning_market_scan_enabled(db: Session, owner_id: str, enabled: bool) -> UserSetting:
    if enabled:
        get_or_create_morning_market_watchlist(db, owner_id)
    return set_setting(db, owner_id, MORNING_MARKET_SCAN_ENABLED, "true" if enabled else "false")


def list_morning_market_scan_enabled_target_ids(db: Session) -> list[str]:
    rows = (
        db.query(UserSetting)
        .filter(
            UserSetting.setting_key == MORNING_MARKET_SCAN_ENABLED,
            UserSetting.setting_value == "true",
        )
        .all()
    )
    return [row.user_id for row in rows]


def list_morning_market_scan_enabled_user_ids(db: Session) -> list[str]:
    return list_morning_market_scan_enabled_target_ids(db)


def set_morning_market_scan_schedule(
    db: Session,
    owner_id: str,
    start_time: str,
    end_time: str,
    weekdays: str,
) -> None:
    set_setting(db, owner_id, MORNING_MARKET_SCAN_START, start_time)
    set_setting(db, owner_id, MORNING_MARKET_SCAN_END, end_time)
    set_setting(db, owner_id, MORNING_MARKET_SCAN_WEEKDAYS, weekdays)


def get_morning_market_scan_schedule(db: Session, owner_id: str) -> tuple[str | None, str | None, str | None]:
    start = get_setting(db, owner_id, MORNING_MARKET_SCAN_START)
    end = get_setting(db, owner_id, MORNING_MARKET_SCAN_END)
    weekdays = get_setting(db, owner_id, MORNING_MARKET_SCAN_WEEKDAYS)
    return (
        start.setting_value if start else None,
        end.setting_value if end else None,
        weekdays.setting_value if weekdays else None,
    )


def set_morning_market_scan_conditions(
    db: Session,
    owner_id: str,
    window_minutes: int,
    gain_percent: float,
    volume_limit_lots: float,
) -> None:
    set_setting(db, owner_id, MORNING_MARKET_SCAN_WINDOW_MINUTES, str(window_minutes))
    set_setting(db, owner_id, MORNING_MARKET_SCAN_GAIN_PERCENT, str(gain_percent))
    set_setting(db, owner_id, MORNING_MARKET_SCAN_VOLUME_LIMIT_LOTS, str(volume_limit_lots))


def get_morning_market_scan_conditions(db: Session, owner_id: str) -> tuple[int | None, float | None, float | None]:
    window = get_setting(db, owner_id, MORNING_MARKET_SCAN_WINDOW_MINUTES)
    gain = get_setting(db, owner_id, MORNING_MARKET_SCAN_GAIN_PERCENT)
    volume = get_setting(db, owner_id, MORNING_MARKET_SCAN_VOLUME_LIMIT_LOTS)
    return (
        int(window.setting_value) if window else None,
        float(gain.setting_value) if gain else None,
        float(volume.setting_value) if volume else None,
    )
