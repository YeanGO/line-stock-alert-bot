import secrets

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.scheduler.monitor import run_monitor
from app.services.line_quota_service import LineQuotaError, get_line_quota_status

router = APIRouter(prefix="/admin", tags=["admin"])


def verify_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    admin_token = get_settings().admin_api_token
    if not admin_token:
        raise HTTPException(status_code=403, detail="Admin API token is not configured")
    if not x_admin_token or not secrets.compare_digest(x_admin_token, admin_token):
        raise HTTPException(status_code=401, detail="Invalid admin token")


@router.post("/run-monitor")
def run_monitor_endpoint(db: Session = Depends(get_db)) -> dict[str, int]:
    return run_monitor(db)


@router.get("/line-quota", dependencies=[Depends(verify_admin_token)])
def line_quota_endpoint() -> dict:
    token = get_settings().line_channel_access_token
    if not token:
        raise HTTPException(status_code=503, detail="LINE_CHANNEL_ACCESS_TOKEN is not configured")
    try:
        return get_line_quota_status(token)
    except LineQuotaError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
