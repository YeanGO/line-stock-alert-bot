from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.repositories.watchlist_repository import (
    create_morning_watchlist,
    create_watchlist_from_command,
    deactivate_target_stock_watchlists,
    get_or_create_morning_market_watchlist,
    list_active_watchlists,
    list_active_morning_watchlists,
    list_morning_watchlists,
    list_target_watchlists,
)
from app.services.command_parser import parse_command


def make_session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_create_regular_watchlist_uses_regular_cooldown() -> None:
    session = make_session()

    watchlist = create_watchlist_from_command(
        db=session,
        line_user_id="U_TEST",
        command=parse_command("追蹤 2330 高於 1000"),
        cooldown_minutes=20,
    )

    assert watchlist.cooldown_minutes == 20
    assert watchlist.is_condition_active is False
    assert watchlist.line_target_id == "U_TEST"
    assert watchlist.target_type == "user"


def test_group_watchlists_are_scoped_by_target_id() -> None:
    session = make_session()

    group_watchlist = create_watchlist_from_command(
        db=session,
        line_user_id="U_CREATOR",
        line_target_id="C_GROUP",
        target_type="group",
        created_by_user_id="U_CREATOR",
        command=parse_command("追蹤 2330 高於 1000"),
        cooldown_minutes=20,
    )
    create_watchlist_from_command(
        db=session,
        line_user_id="U_CREATOR",
        line_target_id="U_CREATOR",
        target_type="user",
        created_by_user_id="U_CREATOR",
        command=parse_command("追蹤 2330 高於 1000"),
        cooldown_minutes=20,
    )

    assert group_watchlist.line_target_id == "C_GROUP"
    assert group_watchlist.target_type == "group"
    assert group_watchlist.created_by_user_id == "U_CREATOR"
    assert [row.id for row in list_target_watchlists(session, "C_GROUP")] == [group_watchlist.id]

    deactivated = deactivate_target_stock_watchlists(session, "C_GROUP", "2330.TW")
    assert deactivated == 1
    assert list_target_watchlists(session, "C_GROUP") == []
    assert len(list_target_watchlists(session, "U_CREATOR")) == 1


def test_internal_market_watchlist_is_hidden_from_morning_lists() -> None:
    session = make_session()

    get_or_create_morning_market_watchlist(session, "U_MARKET")

    assert list_morning_watchlists(session, "U_MARKET") == []
    assert list_active_morning_watchlists(session) == []
    assert list_active_watchlists(session) == []


def test_group_morning_watchlist_does_not_appear_in_creator_personal_list() -> None:
    session = make_session()

    group_watchlist = create_morning_watchlist(
        db=session,
        line_user_id="U_CREATOR",
        line_target_id="C_GROUP",
        target_type="group",
        stock_symbol="2330.TW",
        created_by_user_id="U_CREATOR",
        active_weekdays="2,3,4",
        monitor_start_time="09:30",
        monitor_end_time="11:00",
        window_minutes=45,
        target_percent=5.0,
        max_volume_lots=5000.0,
    )

    assert [row.id for row in list_morning_watchlists(session, "C_GROUP")] == [group_watchlist.id]
    assert list_morning_watchlists(session, "U_CREATOR") == []
