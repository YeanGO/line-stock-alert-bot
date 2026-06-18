from contextlib import asynccontextmanager
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from app.config import get_settings
from app.database import SessionLocal, init_db
from app.routers import admin, line_webhook
from app.scheduler.monitor import run_monitor
from app.services.morning_scan_service import run_morning_gain_low_volume_scan

logging.basicConfig(level=logging.INFO)
settings = get_settings()
scheduler = AsyncIOScheduler()


def scheduled_monitor() -> None:
    db = SessionLocal()
    try:
        run_monitor(db)
    finally:
        db.close()


def scheduled_morning_scan() -> None:
    db = SessionLocal()
    try:
        run_morning_gain_low_volume_scan(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if not scheduler.running:
        scheduler.add_job(
            scheduled_monitor,
            "interval",
            seconds=settings.monitor_interval_seconds or settings.monitor_interval_minutes * 60,
            id="stock-monitor",
            replace_existing=True,
        )
        scheduler.add_job(
            scheduled_morning_scan,
            "interval",
            seconds=settings.scan_interval_seconds,
            id="morning-gain-low-volume-scan",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            misfire_grace_time=60,
        )
        scheduler.start()
    try:
        yield
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=False)


app = FastAPI(title="LINE Stock Alert Bot", version="0.1.0", lifespan=lifespan)
app.include_router(line_webhook.router)
app.include_router(admin.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
