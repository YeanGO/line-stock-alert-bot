import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhook import MessageEvent, WebhookParser
from linebot.v3.webhooks.models import TextMessageContent
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.repositories.user_repository import get_or_create_user
from app.repositories.user_setting_repository import (
    get_morning_market_scan_conditions,
    get_morning_market_scan_schedule,
    is_morning_market_scan_enabled,
    set_morning_market_scan_enabled,
    set_morning_market_scan_conditions,
    set_morning_market_scan_schedule,
)
from app.repositories.watchlist_repository import (
    create_morning_watchlist,
    create_watchlist_from_command,
    deactivate_morning_watchlist,
    deactivate_target_stock_watchlists,
    get_morning_watchlist,
    list_morning_watchlists,
    list_target_watchlists,
)
from app.services.command_parser import CommandParseError, normalize_stock_symbol, parse_command
from app.services.line_service import reply_text

logger = logging.getLogger(__name__)
router = APIRouter(tags=["line"])

WEEKDAY_LABELS = {"0": "週一", "1": "週二", "2": "週三", "3": "週四", "4": "週五", "5": "週六", "6": "週日"}


def format_weekdays(value: str | None) -> str:
    if not value:
        return "週四週五"
    return "".join(WEEKDAY_LABELS.get(item, item) for item in value.split(",") if item)


HELP_TEXT = "\n".join(
    [
        "LINE Stock Alert Bot",
        "追蹤 2330 高於 1000",
        "追蹤 2330 低於 900",
        "追蹤 2330 漲幅超過 3",
        "追蹤 2330 跌幅超過 3",
        "追蹤 2330 成交量放大 2",
        "追蹤 2330 突破均線 MA20",
        "監控早盤 2330 20 8 2500 週三週四週五 09:30-11:00",
        "早盤清單",
        "刪除早盤 2330",
        "取消早盤 2330",
        "開啟早盤全市場",
        "關閉早盤全市場",
        "設定早盤全市場條件 20 8 2500",
        "設定早盤全市場時間 週三週四週五 09:30-11:00",
        "早盤設定",
        "查看追蹤",
        "刪除 2330",
        "狀態",
        "help",
    ]
)


def _format_watchlist_rows(rows: list) -> str:
    if not rows:
        return "目前沒有啟用中的追蹤條件。"

    lines = ["啟用中的追蹤條件："]
    for row in rows:
        if row.condition_type == "intraday_momentum_volume_cap":
            lines.append(
                f"#{row.id} {row.stock_symbol} 動能追蹤 "
                f"{row.window_minutes}分鐘漲幅>={row.target_percent}% "
                f"成交量<={row.max_volume_lots}張 "
                f"{row.monitor_start_time}-{row.monitor_end_time} weekdays={row.active_weekdays}"
            )
            continue
        target = row.target_price or row.target_percent or row.target_multiplier or f"MA{row.ma_period}"
        lines.append(f"#{row.id} {row.stock_symbol} {row.condition_type} {target}")
    return "\n".join(lines)


def _format_morning_watchlist_rows(rows: list) -> str:
    if not rows:
        return "目前沒有早盤急漲低量監控股票"
    lines = ["早盤急漲低量清單："]
    for row in rows:
        lines.append(
            f"{row.stock_symbol.replace('.TW', '')} "
            f"{format_weekdays(row.active_weekdays)} {row.monitor_start_time}-{row.monitor_end_time} "
            f"{row.window_minutes or 20}分鐘漲幅>={row.target_percent or 8}% "
            f"總成交量<={row.max_volume_lots or 2500}張"
        )
    return "\n".join(lines)


def _format_morning_settings(db: Session, line_user_id: str, target_id: str) -> str:
    enabled = is_morning_market_scan_enabled(db, target_id)
    start_time, end_time, weekdays = get_morning_market_scan_schedule(db, target_id)
    window_minutes, gain_percent, volume_limit_lots = get_morning_market_scan_conditions(db, target_id)
    rows = list_morning_watchlists(db, target_id)
    watchlist_text = "\n".join(
        f"{row.stock_symbol.replace('.TW', '')} {format_weekdays(row.active_weekdays)} "
        f"{row.monitor_start_time}-{row.monitor_end_time} "
        f"{row.window_minutes or 20}分鐘漲幅>={row.target_percent or 8}% "
        f"總成交量<={row.max_volume_lots or 2500}張"
        for row in rows
    )
    if not watchlist_text:
        watchlist_text = "目前沒有早盤監控股票"
    status = "開啟" if enabled else "關閉"
    return (
        "早盤監控設定：\n"
        f"全市場通知：{status}\n"
        f"全市場時間：{format_weekdays(weekdays)} {start_time}-{end_time}\n\n"
        f"全市場條件：{window_minutes}分鐘漲幅 >= {gain_percent}%，"
        f"總成交量 <= {volume_limit_lots}張\n\n"
        f"早盤監控清單：\n{watchlist_text}"
    )


def handle_text_command(
    db: Session,
    line_user_id: str,
    text: str,
    line_target_id: str | None = None,
    target_type: str = "user",
) -> str:
    settings = get_settings()
    target_id = line_target_id or line_user_id

    try:
        command = parse_command(text, settings.stock_symbol_suffix)
    except (CommandParseError, ValueError):
        return "指令無法解析，請重新輸入"

    get_or_create_user(db, line_user_id)

    if command.action == "help":
        return HELP_TEXT
    if command.action == "status":
        return "Bot is running. Use 查看追蹤 to list active alerts."
    if command.action == "morning_market_enable":
        set_morning_market_scan_enabled(db, target_id, True)
        return "已開啟早盤全市場通知\n符合條件的全市場股票也會通知你"
    if command.action == "morning_market_disable":
        set_morning_market_scan_enabled(db, target_id, False)
        return "已關閉早盤全市場通知\n之後只會通知你早盤監控清單中的股票"
    if command.action == "morning_market_schedule":
        set_morning_market_scan_schedule(
            db,
            target_id,
            command.monitor_start_time or "09:00",
            command.monitor_end_time or "10:30",
            command.active_weekdays or "3,4",
        )
        return (
            "已設定早盤全市場時間\n"
            f"{format_weekdays(command.active_weekdays)} {command.monitor_start_time}-{command.monitor_end_time}"
        )
    if command.action == "morning_market_conditions":
        set_morning_market_scan_conditions(
            db,
            target_id,
            command.window_minutes or 20,
            command.target_percent or 8.0,
            command.max_volume_lots or 2500.0,
        )
        return (
            "已設定早盤全市場條件\n"
            f"{command.window_minutes or 20}分鐘漲幅 >= {command.target_percent or 8.0}%，"
            f"總成交量 <= {command.max_volume_lots or 2500.0}張"
        )
    if command.action == "morning_settings":
        return _format_morning_settings(db, line_user_id, target_id)
    if command.action == "morning_list":
        return _format_morning_watchlist_rows(list_morning_watchlists(db, target_id))
    if command.action == "morning_delete" and command.stock_symbol:
        count = deactivate_morning_watchlist(db, target_id, command.stock_symbol)
        if count == 0:
            return f"{command.stock_symbol.replace('.TW', '')} 不在早盤急漲低量清單中"
        return f"已刪除早盤急漲低量監控 {command.stock_symbol.replace('.TW', '')}"
    if command.action == "morning_add" and command.stock_symbol:
        existing = get_morning_watchlist(db, target_id, command.stock_symbol)
        if existing is not None:
            return f"{command.stock_symbol.replace('.TW', '')} 已在早盤急漲低量清單中"
        watchlist = create_morning_watchlist(
            db=db,
            line_user_id=line_user_id,
            line_target_id=target_id,
            target_type=target_type,
            stock_symbol=command.stock_symbol,
            created_by_user_id=line_user_id,
            active_weekdays=command.active_weekdays or "3,4",
            monitor_start_time=command.monitor_start_time or "09:00",
            monitor_end_time=command.monitor_end_time or "10:30",
            window_minutes=command.window_minutes or 20,
            target_percent=command.target_percent or 8.0,
            max_volume_lots=command.max_volume_lots or 2500.0,
        )
        return (
            f"已新增早盤急漲低量監控 {watchlist.stock_symbol.replace('.TW', '')}\n"
            f"條件：{format_weekdays(watchlist.active_weekdays)} "
            f"{watchlist.monitor_start_time}-{watchlist.monitor_end_time}，"
            f"{watchlist.window_minutes}分鐘漲幅 >= {watchlist.target_percent}%，"
            f"總成交量 <= {watchlist.max_volume_lots}張"
        )
    if command.action == "list":
        return _format_watchlist_rows(list_target_watchlists(db, target_id))
    if command.action == "delete" and command.stock_symbol:
        count = deactivate_target_stock_watchlists(db, target_id, command.stock_symbol)
        return f"已停用 {count} 筆 {command.stock_symbol} 追蹤條件。"
    if command.action == "add":
        cooldown_minutes = (
            settings.dynamic_cooldown_minutes
            if command.condition_type == "intraday_momentum_volume_cap"
            else settings.default_cooldown_minutes
        )
        watchlist = create_watchlist_from_command(
            db=db,
            line_user_id=line_user_id,
            line_target_id=target_id,
            target_type=target_type,
            created_by_user_id=line_user_id,
            command=command,
            cooldown_minutes=cooldown_minutes,
        )
        if watchlist.condition_type == "intraday_momentum_volume_cap":
            return (
                f"已新增動能追蹤 #{watchlist.id}: {watchlist.stock_symbol}\n"
                f"{watchlist.window_minutes}分鐘漲幅 >= {watchlist.target_percent}%\n"
                f"成交量 <= {watchlist.max_volume_lots}張\n"
                f"監控時間 {watchlist.monitor_start_time}-{watchlist.monitor_end_time}"
            )
        return f"已新增追蹤 #{watchlist.id}: {watchlist.stock_symbol} {watchlist.condition_type}"

    return HELP_TEXT


def _source_value(source: Any, *names: str) -> Any:
    for name in names:
        if isinstance(source, dict):
            value = source.get(name)
        else:
            value = getattr(source, name, None)
        if value:
            return value
    return None


def _extract_source_ids(source: Any) -> tuple[str | None, str | None, str]:
    source_type = _source_value(source, "type") or "user"
    user_id = _source_value(source, "userId", "user_id")
    if source_type == "group":
        return user_id, _source_value(source, "groupId", "group_id"), "group"
    if source_type == "room":
        return user_id, _source_value(source, "roomId", "room_id"), "room"
    return user_id, user_id, "user"


def _handle_raw_line_event(db: Session, event: dict[str, Any]) -> None:
    message = event.get("message") or {}
    if event.get("type") != "message" or message.get("type") != "text":
        return

    line_user_id, line_target_id, target_type = _extract_source_ids(event.get("source") or {})
    reply_token = event.get("replyToken")
    text = message.get("text")
    if not line_user_id or not line_target_id or not reply_token or not text:
        logger.warning("LINE event missing userId, targetId, replyToken, or text: %s", event)
        return

    response_text = handle_text_command(db, line_user_id, text, line_target_id, target_type)
    reply_text(reply_token, response_text)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_line_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    body = (await request.body()).decode("utf-8")

    if not settings.line_channel_secret:
        logger.warning("LINE_CHANNEL_SECRET is not configured; parsing webhook without signature validation")
        payload = json.loads(body)
        for event in payload.get("events", []):
            _handle_raw_line_event(db, event)
        return {"status": "ok"}

    if not x_line_signature:
        raise HTTPException(status_code=400, detail="Missing LINE signature")

    parser = WebhookParser(settings.line_channel_secret)
    try:
        events = parser.parse(body, x_line_signature)
    except InvalidSignatureError as exc:
        raise HTTPException(status_code=400, detail="Invalid LINE signature") from exc

    for event in events:
        if not isinstance(event, MessageEvent) or not isinstance(event.message, TextMessageContent):
            continue

        line_user_id, line_target_id, source_type = _extract_source_ids(event.source)

        if not line_user_id or not line_target_id:
            logger.warning("LINE parsed event missing userId or targetId: source=%s", event.source)
            continue

        response_text = handle_text_command(db, line_user_id, event.message.text, line_target_id, source_type)
        reply_text(event.reply_token, response_text)

    return {"status": "ok"}


@router.post("/webhook/dev-command")
def dev_command(
    line_user_id: str,
    text: str,
    line_target_id: str | None = None,
    target_type: str = "user",
    db: Session = Depends(get_db),
) -> dict[str, str]:
    stock_text = text
    if text.startswith("刪除 "):
        parts = text.split(maxsplit=1)
        stock_text = f"刪除 {normalize_stock_symbol(parts[1])}"
    return {"reply": handle_text_command(db, line_user_id, stock_text, line_target_id, target_type)}
