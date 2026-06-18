import pytest

from app.services.command_parser import CommandParseError, parse_command


def test_parse_price_above() -> None:
    command = parse_command("追蹤 2330 高於 1000")
    assert command.action == "add"
    assert command.stock_symbol == "2330.TW"
    assert command.condition_type == "price_above"
    assert command.target_price == 1000


def test_parse_price_below() -> None:
    command = parse_command("追蹤 2330 低於 900")
    assert command.condition_type == "price_below"
    assert command.target_price == 900


def test_parse_change_percent_above() -> None:
    command = parse_command("追蹤 2330 漲幅超過 3")
    assert command.condition_type == "change_percent_above"
    assert command.target_percent == 3


def test_parse_change_percent_below() -> None:
    command = parse_command("追蹤 2330 跌幅超過 3")
    assert command.condition_type == "change_percent_below"
    assert command.target_percent == 3


def test_parse_volume_spike() -> None:
    command = parse_command("追蹤 2330 成交量放大 2")
    assert command.condition_type == "volume_spike"
    assert command.target_multiplier == 2


def test_parse_ma_breakout() -> None:
    command = parse_command("追蹤 2330 突破均線 MA20")
    assert command.condition_type == "ma_breakout"
    assert command.ma_period == 20


def test_parse_list_and_delete_commands() -> None:
    assert parse_command("查看追蹤").action == "list"
    delete = parse_command("刪除 2330")
    assert delete.action == "delete"
    assert delete.stock_symbol == "2330.TW"


def test_parse_default_momentum_command() -> None:
    command = parse_command("動能追蹤 2330")
    assert command.action == "add"
    assert command.stock_symbol == "2330.TW"
    assert command.condition_type == "intraday_momentum_volume_cap"
    assert command.target_percent == 8
    assert command.max_volume_lots == 2500
    assert command.window_minutes == 20
    assert command.active_weekdays == "3,4"
    assert command.monitor_start_time == "09:00"
    assert command.monitor_end_time == "10:30"


def test_parse_custom_momentum_command() -> None:
    command = parse_command("動能追蹤 2330 9 1800 15 週四週五 09:10-10:20")
    assert command.condition_type == "intraday_momentum_volume_cap"
    assert command.target_percent == 9
    assert command.max_volume_lots == 1800
    assert command.window_minutes == 15
    assert command.active_weekdays == "3,4"
    assert command.monitor_start_time == "09:10"
    assert command.monitor_end_time == "10:20"


def test_parse_morning_add_command_defaults() -> None:
    command = parse_command("早盤急漲 2330")
    assert command.action == "morning_add"
    assert command.stock_symbol == "2330.TW"
    assert command.condition_type == "MORNING_GAIN_LOW_VOLUME"
    assert command.window_minutes == 20
    assert command.target_percent == 8
    assert command.max_volume_lots == 2500
    assert command.active_weekdays == "3,4"
    assert command.monitor_start_time == "09:00"
    assert command.monitor_end_time == "10:30"


def test_parse_morning_add_command_with_time() -> None:
    command = parse_command("監控早盤 2330 09:30-11:00")
    assert command.action == "morning_add"
    assert command.stock_symbol == "2330.TW"
    assert command.active_weekdays == "3,4"
    assert command.monitor_start_time == "09:30"
    assert command.monitor_end_time == "11:00"


def test_parse_morning_add_command_with_weekdays_and_time() -> None:
    command = parse_command("監控早盤 2330 週三週四週五 09:30-11:00")
    assert command.action == "morning_add"
    assert command.active_weekdays == "2,3,4"
    assert command.monitor_start_time == "09:30"
    assert command.monitor_end_time == "11:00"


def test_parse_morning_add_command_with_custom_conditions() -> None:
    command = parse_command("監控早盤 2330 15 6 1800 週三週四週五 09:30-11:00")
    assert command.action == "morning_add"
    assert command.window_minutes == 15
    assert command.target_percent == 6
    assert command.max_volume_lots == 1800
    assert command.active_weekdays == "2,3,4"
    assert command.monitor_start_time == "09:30"
    assert command.monitor_end_time == "11:00"


def test_parse_morning_add_rejects_time_range_as_symbol() -> None:
    with pytest.raises(CommandParseError):
        parse_command("監控早盤 09:00-13:30")


def test_parse_morning_list_delete_and_market_setting_commands() -> None:
    assert parse_command("早盤清單").action == "morning_list"
    assert parse_command("刪除早盤 2330").action == "morning_delete"
    assert parse_command("取消早盤 2330").action == "morning_delete"
    assert parse_command("開啟早盤全市場").action == "morning_market_enable"
    assert parse_command("關閉早盤全市場").action == "morning_market_disable"
    assert parse_command("早盤設定").action == "morning_settings"


def test_parse_morning_market_schedule_commands() -> None:
    command = parse_command("設定早盤全市場時間 09:30-11:00")
    assert command.action == "morning_market_schedule"
    assert command.active_weekdays == "3,4"
    assert command.monitor_start_time == "09:30"
    assert command.monitor_end_time == "11:00"

    command = parse_command("設定早盤全市場時間 週三週四週五 09:30-11:00")
    assert command.active_weekdays == "2,3,4"
    assert command.monitor_start_time == "09:30"
    assert command.monitor_end_time == "11:00"


def test_parse_morning_market_condition_command() -> None:
    command = parse_command("設定早盤全市場條件 15 6 1800")
    assert command.action == "morning_market_conditions"
    assert command.window_minutes == 15
    assert command.target_percent == 6
    assert command.max_volume_lots == 1800


def test_invalid_command() -> None:
    with pytest.raises(CommandParseError):
        parse_command("隨便說")
