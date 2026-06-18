from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    import app.models.alert_history  # noqa: F401
    import app.models.user  # noqa: F401
    import app.models.user_setting  # noqa: F401
    import app.models.watchlist  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_watchlist_columns()


def _ensure_sqlite_watchlist_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "watchlists" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("watchlists")}
    required_columns = {
        "line_target_id": "VARCHAR(128)",
        "target_type": "VARCHAR(16) DEFAULT 'user' NOT NULL",
        "created_by_user_id": "VARCHAR(128)",
        "rule_type": "VARCHAR(64) DEFAULT 'PRICE_ALERT' NOT NULL",
        "window_minutes": "INTEGER",
        "max_volume_lots": "FLOAT",
        "active_weekdays": "VARCHAR(32)",
        "monitor_start_time": "VARCHAR(8)",
        "monitor_end_time": "VARCHAR(8)",
        "is_condition_active": "BOOLEAN DEFAULT 0 NOT NULL",
    }

    with engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE watchlists ADD COLUMN {column_name} {column_type}"))
        connection.execute(text("UPDATE watchlists SET line_target_id = line_user_id WHERE line_target_id IS NULL"))
        connection.execute(text("UPDATE watchlists SET target_type = 'user' WHERE target_type IS NULL OR target_type = ''"))
        connection.execute(
            text("UPDATE watchlists SET created_by_user_id = line_user_id WHERE created_by_user_id IS NULL")
        )
        connection.execute(text("UPDATE watchlists SET rule_type = 'PRICE_ALERT' WHERE rule_type IS NULL OR rule_type = ''"))

    _ensure_sqlite_alert_history_columns()


def _ensure_sqlite_alert_history_columns() -> None:
    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)
    if "alert_history" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("alert_history")}
    required_columns = {
        "line_target_id": "VARCHAR(128)",
        "alert_type": "VARCHAR(64)",
        "alert_date": "VARCHAR(10)",
        "price_20m_ago": "FLOAT",
        "gain_20m": "FLOAT",
        "volume_lots": "FLOAT",
    }

    with engine.begin() as connection:
        for column_name, column_type in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(text(f"ALTER TABLE alert_history ADD COLUMN {column_name} {column_type}"))
        connection.execute(text("UPDATE alert_history SET line_target_id = line_user_id WHERE line_target_id IS NULL"))
