from uuid import uuid4

from fastapi.testclient import TestClient
from linebot.v3.webhooks.models.group_source import GroupSource

from app.main import app
from app.database import SessionLocal
from app.repositories.user_setting_repository import is_morning_market_scan_enabled
from app.routers.line_webhook import _extract_source_ids


def test_extract_source_ids_from_sdk_group_source() -> None:
    line_user_id, line_target_id, target_type = _extract_source_ids(GroupSource(user_id="U_CREATOR", group_id="C_GROUP"))

    assert line_user_id == "U_CREATOR"
    assert line_target_id == "C_GROUP"
    assert target_type == "group"


def test_dev_command_returns_simple_parse_error() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": "U_TEST_PARSE_ERROR", "text": "Unsupported command"},
        )

    assert response.status_code == 200
    assert response.json() == {"reply": "指令無法解析，請重新輸入"}


def test_help_includes_morning_commands() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": "U_TEST_HELP", "text": "help"},
        )

    reply = response.json()["reply"]
    assert "監控早盤 2330 20 8 2500 週三週四週五 09:30-11:00" in reply
    assert "設定早盤全市場條件 20 8 2500" in reply
    assert "設定早盤全市場時間 週三週四週五 09:30-11:00" in reply
    assert "早盤設定" in reply
    assert "早盤急漲 2330" not in reply


def test_dev_command_can_create_group_scoped_watchlist() -> None:
    target_id = f"C_TEST_GROUP_{uuid4().hex}"
    with TestClient(app) as client:
        response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": "U_TEST_GROUP_CREATOR",
                "line_target_id": target_id,
                "target_type": "group",
                "text": "追蹤 2330 高於 1000",
            },
        )
        list_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": "U_TEST_GROUP_CREATOR",
                "line_target_id": target_id,
                "target_type": "group",
                "text": "查看追蹤",
            },
        )

    assert response.status_code == 200
    assert "2330.TW" in response.json()["reply"]
    assert list_response.status_code == 200
    assert "2330.TW" in list_response.json()["reply"]


def test_dev_command_can_manage_morning_watchlist_with_custom_time() -> None:
    target_id = f"C_TEST_MORNING_GROUP_{uuid4().hex}"
    with TestClient(app) as client:
        add_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": "U_TEST_MORNING_CREATOR",
                "line_target_id": target_id,
                "target_type": "group",
                "text": "監控早盤 2330 週三週四週五 09:30-11:00",
            },
        )
        duplicate_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": "U_TEST_MORNING_CREATOR",
                "line_target_id": target_id,
                "target_type": "group",
                "text": "急漲低量 2330",
            },
        )
        list_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": "U_TEST_MORNING_CREATOR",
                "line_target_id": target_id,
                "target_type": "group",
                "text": "早盤清單",
            },
        )
        delete_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": "U_TEST_MORNING_CREATOR",
                "line_target_id": target_id,
                "target_type": "group",
                "text": "取消早盤 2330",
            },
        )

    assert "已新增早盤急漲低量監控 2330" in add_response.json()["reply"]
    assert "週三週四週五 09:30-11:00" in add_response.json()["reply"]
    assert "2330 已在早盤急漲低量清單中" in duplicate_response.json()["reply"]
    assert "2330 週三週四週五 09:30-11:00" in list_response.json()["reply"]
    assert "已刪除早盤急漲低量監控 2330" in delete_response.json()["reply"]


def test_dev_command_can_manage_morning_market_scan_setting_and_schedule() -> None:
    user_id = f"U_TEST_MARKET_{uuid4().hex}"
    with TestClient(app) as client:
        enable_response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "開啟早盤全市場"},
        )
        schedule_response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "設定早盤全市場時間 週三週四週五 09:30-11:00"},
        )
        settings_response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "早盤設定"},
        )
        disable_response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "關閉早盤全市場"},
        )

    assert enable_response.json()["reply"] == "已開啟早盤全市場通知\n符合條件的全市場股票也會通知你"
    assert "週三週四週五 09:30-11:00" in schedule_response.json()["reply"]
    assert "全市場通知：開啟" in settings_response.json()["reply"]
    assert "全市場時間：週三週四週五 09:30-11:00" in settings_response.json()["reply"]
    assert disable_response.json()["reply"] == "已關閉早盤全市場通知\n之後只會通知你早盤監控清單中的股票"


def test_group_morning_market_scan_settings_are_scoped_to_group() -> None:
    user_id = f"U_TEST_GROUP_MARKET_{uuid4().hex}"
    group_id = f"C_TEST_GROUP_MARKET_{uuid4().hex}"
    with TestClient(app) as client:
        enable_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": user_id,
                "line_target_id": group_id,
                "target_type": "group",
                "text": "開啟早盤全市場",
            },
        )
        client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": user_id,
                "line_target_id": group_id,
                "target_type": "group",
                "text": "設定早盤全市場條件 15 6 1800",
            },
        )
        settings_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": user_id,
                "line_target_id": group_id,
                "target_type": "group",
                "text": "早盤設定",
            },
        )

    db = SessionLocal()
    try:
        assert is_morning_market_scan_enabled(db, group_id) is True
        assert is_morning_market_scan_enabled(db, user_id) is False
    finally:
        db.close()

    assert enable_response.json()["reply"] == "已開啟早盤全市場通知\n符合條件的全市場股票也會通知你"
    assert "全市場通知：開啟" in settings_response.json()["reply"]
    assert "全市場條件：15分鐘漲幅 >= 6.0%，總成交量 <= 1800.0張" in settings_response.json()["reply"]
