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


def test_momentum_commands_are_removed() -> None:
    with pytest.raises(CommandParseError):
        parse_command("動能追蹤 2330")

    with pytest.raises(CommandParseError):
        parse_command("盤中追蹤 2330 9 1800 15 週四週五 09:10-10:20")


def test_parse_morning_add_rejects_missing_conditions() -> None:
    for text in ["早盤急漲 2330", "監控早盤 2330", "監控早盤 2330 09:30-11:00"]:
        with pytest.raises(CommandParseError):
            parse_command(text)


def test_parse_morning_add_command_with_custom_conditions() -> None:
    command = parse_command("監控早盤 2330 45 5 5000 週一週二 09:00-13:30")
    assert command.action == "morning_add"
    assert command.window_minutes == 45
    assert command.target_percent == 5
    assert command.max_volume_lots == 5000
    assert command.active_weekdays == "0,1"
    assert command.monitor_start_time == "09:00"
    assert command.monitor_end_time == "13:30"


def test_parse_morning_add_rejects_time_range_as_symbol() -> None:
    with pytest.raises(CommandParseError):
        parse_command("監控早盤 09:00-13:30")


def test_parse_morning_list_delete_and_market_setting_commands() -> None:
    assert parse_command("早盤清單").action == "morning_list"
    assert parse_command("刪除早盤 2330").action == "morning_delete"
    with pytest.raises(CommandParseError):
        parse_command("取消早盤 2330")
    assert parse_command("開啟早盤全市場").action == "morning_market_enable"
    assert parse_command("關閉早盤全市場").action == "morning_market_disable"
    assert parse_command("早盤設定").action == "morning_settings"


def test_parse_morning_market_schedule_commands() -> None:
    with pytest.raises(CommandParseError):
        parse_command("設定早盤全市場時間 09:30-11:00")

    command = parse_command("設定早盤全市場時間 週一週二 09:00-13:30")
    assert command.action == "morning_market_schedule"
    assert command.active_weekdays == "0,1"
    assert command.monitor_start_time == "09:00"
    assert command.monitor_end_time == "13:30"


def test_parse_morning_market_condition_command() -> None:
    command = parse_command("設定早盤全市場條件 45 5 5000")
    assert command.action == "morning_market_conditions"
    assert command.window_minutes == 45
    assert command.target_percent == 5
    assert command.max_volume_lots == 5000


def test_invalid_command() -> None:
    with pytest.raises(CommandParseError):
        parse_command("隨便說")
