from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from linebot.v3.webhooks.models.group_source import GroupSource

from app.database import SessionLocal
from app.main import app
from app.models.alert_history import AlertHistory
from app.models.user import User
from app.models.user_setting import UserSetting
from app.models.watchlist import Watchlist
from app.repositories.user_setting_repository import is_morning_market_scan_enabled
from app.routers.line_webhook import _extract_source_ids


def _cleanup_test_rows() -> None:
    db = SessionLocal()
    try:
        db.query(AlertHistory).filter(
            AlertHistory.line_target_id.like("C_TEST%")
            | AlertHistory.line_target_id.like("U_TEST%")
            | AlertHistory.line_user_id.like("U_TEST%")
        ).delete(synchronize_session=False)
        db.query(Watchlist).filter(
            Watchlist.line_target_id.like("C_TEST%")
            | Watchlist.line_target_id.like("U_TEST%")
            | Watchlist.line_user_id.like("U_TEST%")
            | Watchlist.line_user_id.like("C_TEST%")
        ).delete(synchronize_session=False)
        db.query(UserSetting).filter(
            UserSetting.user_id.like("C_TEST%")
            | UserSetting.user_id.like("U_TEST%")
        ).delete(synchronize_session=False)
        db.query(User).filter(User.line_user_id.like("U_TEST%")).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def cleanup_line_webhook_test_rows():
    _cleanup_test_rows()
    yield
    _cleanup_test_rows()


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
    assert "監控早盤 2330 45 5 5000 週一週二 09:00-13:30" in reply
    assert "設定早盤全市場條件 45 5 5000" in reply
    assert "設定早盤全市場時間 週一週二 09:00-13:30" in reply
    assert "早盤設定" in reply
    assert "早盤急漲 2330" not in reply
    assert "取消早盤 2330" not in reply
    assert "動能追蹤" not in reply


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
                "text": "監控早盤 2330 45 5 5000 週三週四週五 09:30-11:00",
            },
        )
        duplicate_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": "U_TEST_MORNING_CREATOR",
                "line_target_id": target_id,
                "target_type": "group",
                "text": "監控早盤 2330 45 5 5000 週三週四週五 09:30-11:00",
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
                "text": "刪除早盤 2330",
            },
        )

    assert "已新增早盤急漲低量監控 2330" in add_response.json()["reply"]
    assert "週三週四週五 09:30-11:00" in add_response.json()["reply"]
    assert "45分鐘漲幅 >= 5.0%" in add_response.json()["reply"]
    assert "2330 已在早盤急漲低量清單中" in duplicate_response.json()["reply"]
    assert "2330 週三週四週五 09:30-11:00" in list_response.json()["reply"]
    assert "已刪除早盤急漲低量監控 2330" in delete_response.json()["reply"]


def test_cancel_morning_command_is_removed() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": "U_TEST_CANCEL_MORNING", "text": "取消早盤 2330"},
        )

    assert response.json()["reply"] == "指令無法解析，請重新輸入"


def test_group_morning_watchlist_is_not_listed_in_personal_chat() -> None:
    user_id = f"U_TEST_SCOPE_{uuid4().hex}"
    group_id = f"C_TEST_SCOPE_{uuid4().hex}"
    with TestClient(app) as client:
        client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": user_id,
                "line_target_id": group_id,
                "target_type": "group",
                "text": "監控早盤 2330 45 5 5000 週三週四週五 09:30-11:00",
            },
        )
        group_list_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": user_id,
                "line_target_id": group_id,
                "target_type": "group",
                "text": "早盤清單",
            },
        )
        personal_list_response = client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": user_id,
                "text": "早盤清單",
            },
        )

    assert "2330" in group_list_response.json()["reply"]
    assert personal_list_response.json()["reply"] == "目前沒有早盤急漲低量監控股票"


def test_dev_command_can_manage_morning_market_scan_setting_and_schedule() -> None:
    user_id = f"U_TEST_MARKET_{uuid4().hex}"
    with TestClient(app) as client:
        enable_response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "開啟早盤全市場"},
        )
        schedule_response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "設定早盤全市場時間 週一週二 09:00-13:30"},
        )
        condition_response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "設定早盤全市場條件 45 5 5000"},
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
    assert "週一週二 09:00-13:30" in schedule_response.json()["reply"]
    assert "45分鐘漲幅 >= 5.0%，總成交量 <= 5000.0張" in condition_response.json()["reply"]
    assert "全市場通知：開啟" in settings_response.json()["reply"]
    assert "全市場時間：週一週二 09:00-13:30" in settings_response.json()["reply"]
    assert "全市場條件：45分鐘漲幅 >= 5.0%，總成交量 <= 5000.0張" in settings_response.json()["reply"]
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
                "text": "設定早盤全市場條件 45 5 5000",
            },
        )
        client.post(
            "/webhook/dev-command",
            params={
                "line_user_id": user_id,
                "line_target_id": group_id,
                "target_type": "group",
                "text": "設定早盤全市場時間 週一週二 09:00-13:30",
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
    assert "全市場條件：45分鐘漲幅 >= 5.0%，總成交量 <= 5000.0張" in settings_response.json()["reply"]


def test_morning_settings_show_unset_market_schedule_and_conditions() -> None:
    user_id = f"U_TEST_UNSET_MARKET_{uuid4().hex}"
    with TestClient(app) as client:
        client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "開啟早盤全市場"},
        )
        settings_response = client.post(
            "/webhook/dev-command",
            params={"line_user_id": user_id, "text": "早盤設定"},
        )

    reply = settings_response.json()["reply"]
    assert "全市場時間：未設定" in reply
    assert "全市場條件：未設定" in reply
