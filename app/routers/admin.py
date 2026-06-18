from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.scheduler.monitor import run_monitor

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/run-monitor")
def run_monitor_endpoint(db: Session = Depends(get_db)) -> dict[str, int]:
    return run_monitor(db)
