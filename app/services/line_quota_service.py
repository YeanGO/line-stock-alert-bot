import requests


LINE_QUOTA_URL = "https://api.line.me/v2/bot/message/quota"
LINE_QUOTA_USAGE_URL = "https://api.line.me/v2/bot/message/quota/consumption"


class LineQuotaError(RuntimeError):
    pass


def _get_line_json(url: str, headers: dict[str, str]) -> dict:
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except requests.RequestException as exc:
        raise LineQuotaError(f"failed to connect to LINE quota API: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise LineQuotaError(f"LINE quota API returned non-JSON response: HTTP {response.status_code}") from exc

    if not response.ok:
        message = payload.get("message") if isinstance(payload, dict) else None
        raise LineQuotaError(f"LINE quota API failed: HTTP {response.status_code} {message or payload}")
    return payload


def get_line_quota_status(channel_access_token: str) -> dict:
    headers = {"Authorization": f"Bearer {channel_access_token}"}
    quota = _get_line_json(LINE_QUOTA_URL, headers)
    usage = _get_line_json(LINE_QUOTA_USAGE_URL, headers)

    quota_type = quota.get("type")
    limit = quota.get("value") if quota_type == "limited" else None
    total_usage = usage.get("totalUsage")
    remaining = None
    is_exhausted = False
    if isinstance(limit, int) and isinstance(total_usage, int):
        remaining = max(limit - total_usage, 0)
        is_exhausted = total_usage >= limit

    return {
        "quota": {
            "type": quota_type,
            "limit": limit,
            "raw": quota,
        },
        "usage": {
            "total": total_usage,
            "raw": usage,
        },
        "remaining": remaining,
        "is_exhausted": is_exhausted,
    }
