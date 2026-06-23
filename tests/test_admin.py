from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app


def test_line_quota_requires_admin_token(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.admin.get_settings",
        lambda: SimpleNamespace(admin_api_token="secret", line_channel_access_token="line-token"),
    )

    with TestClient(app) as client:
        response = client.get("/admin/line-quota")

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid admin token"


def test_line_quota_rejects_wrong_admin_token(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.admin.get_settings",
        lambda: SimpleNamespace(admin_api_token="secret", line_channel_access_token="line-token"),
    )

    with TestClient(app) as client:
        response = client.get("/admin/line-quota", headers={"X-Admin-Token": "wrong"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid admin token"


def test_line_quota_requires_configured_admin_token(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.admin.get_settings",
        lambda: SimpleNamespace(admin_api_token=None, line_channel_access_token="line-token"),
    )

    with TestClient(app) as client:
        response = client.get("/admin/line-quota", headers={"X-Admin-Token": "secret"})

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin API token is not configured"


def test_line_quota_returns_usage_when_authorized(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routers.admin.get_settings",
        lambda: SimpleNamespace(admin_api_token="secret", line_channel_access_token="line-token"),
    )
    monkeypatch.setattr(
        "app.routers.admin.get_line_quota_status",
        lambda token: {
            "quota": {"type": "limited", "limit": 200, "raw": {"type": "limited", "value": 200}},
            "usage": {"total": 150, "raw": {"totalUsage": 150}},
            "remaining": 50,
            "is_exhausted": False,
        },
    )

    with TestClient(app) as client:
        response = client.get("/admin/line-quota", headers={"X-Admin-Token": "secret"})

    assert response.status_code == 200
    assert response.json()["remaining"] == 50
    assert response.json()["is_exhausted"] is False
