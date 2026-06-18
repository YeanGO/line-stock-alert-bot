from app.models.watchlist import Watchlist
from app.schemas.rule import RuleEvaluation
from app.schemas.stock import StockQuote
from zoneinfo import ZoneInfo


TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def _is_inside_monitor_schedule(watchlist: Watchlist, quote: StockQuote) -> bool:
    updated_at = quote.updated_at
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=TAIPEI_TZ)
    local_time = updated_at.astimezone(TAIPEI_TZ)

    if watchlist.active_weekdays:
        active_weekdays = {int(value) for value in watchlist.active_weekdays.split(",") if value.strip()}
        if local_time.weekday() not in active_weekdays:
            return False

    if watchlist.monitor_start_time and watchlist.monitor_end_time:
        current_hhmm = local_time.strftime("%H:%M")
        return watchlist.monitor_start_time <= current_hhmm <= watchlist.monitor_end_time

    return True


def evaluate_rule(watchlist: Watchlist, quote: StockQuote) -> RuleEvaluation:
    condition_type = watchlist.condition_type

    if condition_type == "price_above":
        if watchlist.target_price is None:
            return RuleEvaluation(triggered=False, reason="missing target_price")
        triggered = quote.current_price >= watchlist.target_price
        return RuleEvaluation(triggered=triggered, reason=f"price {quote.current_price} >= {watchlist.target_price}")

    if condition_type == "price_below":
        if watchlist.target_price is None:
            return RuleEvaluation(triggered=False, reason="missing target_price")
        triggered = quote.current_price <= watchlist.target_price
        return RuleEvaluation(triggered=triggered, reason=f"price {quote.current_price} <= {watchlist.target_price}")

    if condition_type == "change_percent_above":
        if watchlist.target_percent is None or quote.change_percent is None:
            return RuleEvaluation(triggered=False, reason="missing percent data")
        triggered = quote.change_percent >= watchlist.target_percent
        return RuleEvaluation(triggered=triggered, reason=f"change {quote.change_percent}% >= {watchlist.target_percent}%")

    if condition_type == "change_percent_below":
        if watchlist.target_percent is None or quote.change_percent is None:
            return RuleEvaluation(triggered=False, reason="missing percent data")
        triggered = quote.change_percent <= -watchlist.target_percent
        return RuleEvaluation(triggered=triggered, reason=f"change {quote.change_percent}% <= -{watchlist.target_percent}%")

    if condition_type == "volume_spike":
        if watchlist.target_multiplier is None or quote.current_volume is None or quote.avg_volume_5d is None:
            return RuleEvaluation(triggered=False, reason="missing volume data")
        target_volume = quote.avg_volume_5d * watchlist.target_multiplier
        triggered = quote.current_volume >= target_volume
        return RuleEvaluation(triggered=triggered, reason=f"volume {quote.current_volume} >= {target_volume}")

    if condition_type == "ma_breakout":
        if watchlist.ma_period not in {5, 10, 20, 60}:
            return RuleEvaluation(triggered=False, reason="unsupported ma_period")
        current_ma = getattr(quote, f"ma{watchlist.ma_period}")
        previous_ma = getattr(quote, f"previous_ma{watchlist.ma_period}")
        if current_ma is None or previous_ma is None or quote.previous_close is None:
            return RuleEvaluation(triggered=False, reason="missing moving average data")
        triggered = quote.previous_close < previous_ma and quote.current_price >= current_ma
        return RuleEvaluation(
            triggered=triggered,
            reason=f"previous close {quote.previous_close} < MA and current price {quote.current_price} >= MA",
        )

    if condition_type == "intraday_momentum_volume_cap":
        if not _is_inside_monitor_schedule(watchlist, quote):
            return RuleEvaluation(triggered=False, reason="outside monitor schedule")
        if (
            watchlist.target_percent is None
            or watchlist.max_volume_lots is None
            or quote.intraday_change_percent is None
            or quote.intraday_volume is None
        ):
            return RuleEvaluation(triggered=False, reason="missing intraday momentum data")

        target_volume_shares = watchlist.max_volume_lots * 1000
        triggered = (
            quote.intraday_change_percent >= watchlist.target_percent
            and quote.intraday_volume <= target_volume_shares
        )
        return RuleEvaluation(
            triggered=triggered,
            reason=(
                f"{watchlist.window_minutes}m change {quote.intraday_change_percent}% >= {watchlist.target_percent}% "
                f"and volume {quote.intraday_volume / 1000:.0f} lots <= {watchlist.max_volume_lots:.0f} lots"
            ),
        )

    return RuleEvaluation(triggered=False, reason=f"unsupported condition_type: {condition_type}")
