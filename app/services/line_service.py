import logging

from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)

from app.config import get_settings

logger = logging.getLogger(__name__)


def _messaging_api() -> MessagingApi | None:
    token = get_settings().line_channel_access_token
    if not token:
        logger.warning("LINE_CHANNEL_ACCESS_TOKEN is not configured; LINE message skipped")
        return None
    configuration = Configuration(access_token=token)
    return MessagingApi(ApiClient(configuration))


def reply_text(reply_token: str, text: str) -> None:
    api = _messaging_api()
    if api is None:
        return
    api.reply_message(ReplyMessageRequest(reply_token=reply_token, messages=[TextMessage(text=text)]))


def push_text(line_user_id: str, text: str) -> None:
    api = _messaging_api()
    if api is None:
        return
    api.push_message(PushMessageRequest(to=line_user_id, messages=[TextMessage(text=text)]))
