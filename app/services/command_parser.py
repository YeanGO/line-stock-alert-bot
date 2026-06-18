import re

from app.schemas.command import ParsedCommand


_ADD_ALIASES = {"追蹤", "新增", "加入"}
_MOMENTUM_ADD_ALIASES = {"動能追蹤", "盤中追蹤"}
_MORNING_ADD_ALIASES = {"早盤急漲", "急漲低量", "監控早盤"}
_MORNING_LIST_ALIASES = {"早盤清單", "早盤急漲清單"}
_MORNING_DELETE_ALIASES = {"刪除早盤", "取消早盤", "刪除急漲"}
_MORNING_ENABLE_MARKET_ALIASES = {"開啟早盤全市場"}
_MORNING_DISABLE_MARKET_ALIASES = {"關閉早盤全市場"}
_MORNING_SETTING_ALIASES = {"早盤設定"}
_MORNING_SET_MARKET_TIME_ALIASES = {"設定早盤全市場時間", "設定早盤時間"}
_MORNING_SET_MARKET_CONDITION_ALIASES = {"設定早盤全市場條件", "設定早盤條件"}
_LIST_ALIASES = {"查看追蹤", "追蹤清單", "清單", "list"}
_HELP_ALIASES = {"help", "幫助", "說明"}
_STATUS_ALIASES = {"狀態", "status"}
_DELETE_ALIASES = {"刪除", "移除", "取消", "取消動能"}

DEFAULT_MOMENTUM_PERCENT = 8.0
DEFAULT_MOMENTUM_MAX_VOLUME_LOTS = 2500.0
DEFAULT_MOMENTUM_WINDOW_MINUTES = 20
DEFAULT_MOMENTUM_WEEKDAYS = "3,4"
DEFAULT_MOMENTUM_START_TIME = "09:00"
DEFAULT_MOMENTUM_END_TIME = "10:30"


class CommandParseError(ValueError):
    pass


def normalize_stock_symbol(symbol: str, suffix: str = ".TW") -> str:
    value = symbol.strip().upper()
    if "." in value:
        return value
    if re.fullmatch(r"\d{4,6}", value):
        return f"{value}{suffix}"
    return value


def normalize_tw_stock_symbol(symbol: str, suffix: str = ".TW") -> str:
    value = symbol.strip().upper()
    if re.fullmatch(r"\d{4,6}", value):
        return f"{value}{suffix}"
    if re.fullmatch(r"\d{4,6}\.(TW|TWO)", value):
        return value
    raise CommandParseError("Stock symbol must look like 2330 or 2330.TW")


def parse_weekdays(text: str) -> str:
    mapping = {
        "一": 0,
        "二": 1,
        "三": 2,
        "四": 3,
        "五": 4,
        "六": 5,
        "日": 6,
        "天": 6,
    }
    values = [str(value) for label, value in mapping.items() if f"週{label}" in text or f"星期{label}" in text]
    if not values:
        raise CommandParseError("Weekday must look like 週四週五")
    return ",".join(dict.fromkeys(values))


def parse_time_range(text: str) -> tuple[str, str]:
    match = re.fullmatch(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", text)
    if not match:
        raise CommandParseError("Time range must look like 09:00-10:30")
    return match.group(1), match.group(2)


def _parse_optional_schedule(parts: list[str], start_index: int) -> tuple[str, str, str]:
    active_weekdays = DEFAULT_MOMENTUM_WEEKDAYS
    monitor_start_time = DEFAULT_MOMENTUM_START_TIME
    monitor_end_time = DEFAULT_MOMENTUM_END_TIME
    extras = parts[start_index:]
    if len(extras) == 1:
        monitor_start_time, monitor_end_time = parse_time_range(extras[0])
    elif len(extras) >= 2:
        active_weekdays = parse_weekdays(extras[0])
        monitor_start_time, monitor_end_time = parse_time_range(extras[1])
    return active_weekdays, monitor_start_time, monitor_end_time


def _is_number(value: str) -> bool:
    try:
        float(value)
    except ValueError:
        return False
    return True


def parse_command(text: str, stock_symbol_suffix: str = ".TW") -> ParsedCommand:
    raw_text = text.strip()
    if not raw_text:
        raise CommandParseError("Empty command")

    lowered = raw_text.lower()
    if lowered in _HELP_ALIASES or raw_text in _HELP_ALIASES:
        return ParsedCommand(action="help", raw_text=raw_text)
    if raw_text in _LIST_ALIASES or lowered in _LIST_ALIASES:
        return ParsedCommand(action="list", raw_text=raw_text)
    if raw_text in _MORNING_LIST_ALIASES:
        return ParsedCommand(action="morning_list", raw_text=raw_text)
    if raw_text in _MORNING_ENABLE_MARKET_ALIASES:
        return ParsedCommand(action="morning_market_enable", raw_text=raw_text)
    if raw_text in _MORNING_DISABLE_MARKET_ALIASES:
        return ParsedCommand(action="morning_market_disable", raw_text=raw_text)
    if raw_text in _MORNING_SETTING_ALIASES:
        return ParsedCommand(action="morning_settings", raw_text=raw_text)

    parts = raw_text.split()
    action = parts[0]
    if action in _STATUS_ALIASES or lowered in _STATUS_ALIASES:
        return ParsedCommand(action="status", raw_text=raw_text)

    if action in _MORNING_SET_MARKET_TIME_ALIASES:
        if len(parts) < 2:
            raise CommandParseError("Morning market time command requires a time range")
        if len(parts) == 2:
            active_weekdays = DEFAULT_MOMENTUM_WEEKDAYS
            monitor_start_time, monitor_end_time = parse_time_range(parts[1])
        else:
            active_weekdays = parse_weekdays(parts[1])
            monitor_start_time, monitor_end_time = parse_time_range(parts[2])
        return ParsedCommand(
            action="morning_market_schedule",
            active_weekdays=active_weekdays,
            monitor_start_time=monitor_start_time,
            monitor_end_time=monitor_end_time,
            raw_text=raw_text,
        )

    if action in _MORNING_SET_MARKET_CONDITION_ALIASES:
        if len(parts) < 4:
            raise CommandParseError("Morning market condition command requires window, percent, and volume")
        return ParsedCommand(
            action="morning_market_conditions",
            window_minutes=int(parts[1]),
            target_percent=float(parts[2]),
            max_volume_lots=float(parts[3]),
            raw_text=raw_text,
        )

    if action in _MORNING_DELETE_ALIASES:
        if len(parts) < 2:
            raise CommandParseError("Morning delete command requires a stock symbol")
        return ParsedCommand(
            action="morning_delete",
            stock_symbol=normalize_stock_symbol(parts[1], stock_symbol_suffix),
            raw_text=raw_text,
        )

    if action in _DELETE_ALIASES:
        if len(parts) < 2:
            raise CommandParseError("Delete command requires a stock symbol")
        return ParsedCommand(
            action="delete",
            stock_symbol=normalize_stock_symbol(parts[1], stock_symbol_suffix),
            raw_text=raw_text,
        )

    if action in _MORNING_ADD_ALIASES:
        if len(parts) < 2:
            raise CommandParseError("Morning command requires a stock symbol")
        stock_symbol = normalize_tw_stock_symbol(parts[1], stock_symbol_suffix)
        window_minutes = DEFAULT_MOMENTUM_WINDOW_MINUTES
        target_percent = DEFAULT_MOMENTUM_PERCENT
        max_volume_lots = DEFAULT_MOMENTUM_MAX_VOLUME_LOTS
        schedule_start_index = 2
        if len(parts) >= 5 and _is_number(parts[2]) and _is_number(parts[3]) and _is_number(parts[4]):
            window_minutes = int(parts[2])
            target_percent = float(parts[3])
            max_volume_lots = float(parts[4])
            schedule_start_index = 5
        active_weekdays, monitor_start_time, monitor_end_time = _parse_optional_schedule(parts, schedule_start_index)
        return ParsedCommand(
            action="morning_add",
            stock_symbol=stock_symbol,
            condition_type="MORNING_GAIN_LOW_VOLUME",
            target_percent=target_percent,
            max_volume_lots=max_volume_lots,
            window_minutes=window_minutes,
            active_weekdays=active_weekdays,
            monitor_start_time=monitor_start_time,
            monitor_end_time=monitor_end_time,
            raw_text=raw_text,
        )

    if action in _MOMENTUM_ADD_ALIASES:
        if len(parts) < 2:
            raise CommandParseError("Momentum command requires a stock symbol")
        stock_symbol = normalize_stock_symbol(parts[1], stock_symbol_suffix)
        target_percent = float(parts[2]) if len(parts) >= 3 else DEFAULT_MOMENTUM_PERCENT
        max_volume_lots = float(parts[3]) if len(parts) >= 4 else DEFAULT_MOMENTUM_MAX_VOLUME_LOTS
        window_minutes = int(parts[4]) if len(parts) >= 5 else DEFAULT_MOMENTUM_WINDOW_MINUTES
        active_weekdays = parse_weekdays(parts[5]) if len(parts) >= 6 else DEFAULT_MOMENTUM_WEEKDAYS
        if len(parts) >= 7:
            monitor_start_time, monitor_end_time = parse_time_range(parts[6])
        else:
            monitor_start_time = DEFAULT_MOMENTUM_START_TIME
            monitor_end_time = DEFAULT_MOMENTUM_END_TIME

        return ParsedCommand(
            action="add",
            stock_symbol=stock_symbol,
            condition_type="intraday_momentum_volume_cap",
            target_percent=target_percent,
            window_minutes=window_minutes,
            max_volume_lots=max_volume_lots,
            active_weekdays=active_weekdays,
            monitor_start_time=monitor_start_time,
            monitor_end_time=monitor_end_time,
            raw_text=raw_text,
        )

    if action not in _ADD_ALIASES:
        raise CommandParseError("Unsupported command")
    if len(parts) < 4:
        raise CommandParseError("Add command requires stock symbol, condition, and target")

    stock_symbol = normalize_stock_symbol(parts[1], stock_symbol_suffix)
    condition_text = parts[2]
    target = parts[3]

    if condition_text in {"高於", "大於", "突破"}:
        return ParsedCommand(
            action="add",
            stock_symbol=stock_symbol,
            condition_type="price_above",
            target_price=float(target),
            raw_text=raw_text,
        )
    if condition_text in {"低於", "小於", "跌破"}:
        return ParsedCommand(
            action="add",
            stock_symbol=stock_symbol,
            condition_type="price_below",
            target_price=float(target),
            raw_text=raw_text,
        )
    if condition_text in {"漲幅超過", "漲幅"}:
        return ParsedCommand(
            action="add",
            stock_symbol=stock_symbol,
            condition_type="change_percent_above",
            target_percent=float(target),
            raw_text=raw_text,
        )
    if condition_text in {"跌幅超過", "跌幅"}:
        return ParsedCommand(
            action="add",
            stock_symbol=stock_symbol,
            condition_type="change_percent_below",
            target_percent=float(target),
            raw_text=raw_text,
        )
    if condition_text in {"成交量放大", "量增", "爆量"}:
        return ParsedCommand(
            action="add",
            stock_symbol=stock_symbol,
            condition_type="volume_spike",
            target_multiplier=float(target),
            raw_text=raw_text,
        )
    if condition_text in {"突破均線", "站上均線", "均線"}:
        ma_match = re.fullmatch(r"MA(5|10|20|60)", target.upper())
        if not ma_match:
            raise CommandParseError("Moving average condition requires MA5, MA10, MA20, or MA60")
        return ParsedCommand(
            action="add",
            stock_symbol=stock_symbol,
            condition_type="ma_breakout",
            ma_period=int(ma_match.group(1)),
            raw_text=raw_text,
        )

    raise CommandParseError("Unsupported condition")
