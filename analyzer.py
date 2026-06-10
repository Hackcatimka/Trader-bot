import asyncio
import logging
import time
from collections import deque

from config import COOLDOWN_MINUTES
from database import get_all_active_users, load_cooldowns, save_cooldown

logger = logging.getLogger(__name__)

# symbol -> deque[(timestamp, price, vol_delta)]
price_buffer: dict[str, deque] = {}
# symbol -> last seen 24h quote volume (to compute per-tick delta)
_last_q: dict[str, float] = {}
# symbol -> latest 24h quote volume in USDT
current_24h_vol: dict[str, float] = {}

# In-memory cooldowns: (user_id, symbol) -> last signal timestamp
_cooldowns: dict[tuple[int, str], float] = {}

# User cache (refreshed every 5 s to avoid per-tick DB queries)
_users_cache: list[dict] = []
_users_cache_ts: float = 0.0
_USERS_CACHE_TTL = 5.0

_signal_queue: asyncio.Queue | None = None


def init_signal_queue(q: asyncio.Queue) -> None:
    global _signal_queue
    _signal_queue = q


async def init_cooldowns() -> None:
    """Load persisted cooldowns from DB into the in-memory dict at startup."""
    loaded = await load_cooldowns()
    _cooldowns.update(loaded)
    logger.info("Loaded %d cooldowns from DB", len(loaded))


def prefill_from_klines(
    exchange_symbol: str,
    candles: list[tuple[float, float, float]],
    now: float,
) -> None:
    """Pre-populate price_buffer from normalized candles before WS starts.

    candles: [(close_time_seconds, close_price, quote_vol)] ascending.
    """
    buf = price_buffer.setdefault(exchange_symbol, deque())
    for close_time, price, vol in candles:
        if close_time > now:
            close_time = now
        buf.append((close_time, price, vol))


def _persist_cooldown(uid: int, symbol: str, ts: float) -> None:
    """Schedule a fire-and-forget DB write for the cooldown."""
    try:
        asyncio.get_running_loop().create_task(save_cooldown(uid, symbol, ts))
    except RuntimeError:
        pass


async def _get_users() -> list[dict]:
    global _users_cache, _users_cache_ts
    now = time.time()
    if now - _users_cache_ts > _USERS_CACHE_TTL:
        _users_cache = await get_all_active_users()
        _users_cache_ts = now
    return _users_cache


def _window_seconds(users: list[dict]) -> int:
    if not users:
        return 7200
    max_tf = max(u["timeframe"] for u in users)
    return int(max_tf * 2 * 1.2 * 60)


def _check_and_signal(
    symbol: str,
    buf: deque,
    user: dict,
    now: float,
    vol_24h: float,
) -> None:
    if vol_24h < user["min_volume_usd"]:
        return

    tf_secs = user["timeframe"] * 60
    b_start = now - tf_secs
    a_start = now - 2 * tf_secs

    a_vol = 0.0
    b_vol = 0.0
    b_oldest_price: float | None = None
    b_last_price = 0.0
    has_a = False
    has_b = False

    for ts, price, vol in buf:
        if ts < a_start:
            continue
        if ts < b_start:
            a_vol += vol
            has_a = True
        else:
            if b_oldest_price is None:
                b_oldest_price = price
            b_last_price = price
            b_vol += vol
            has_b = True

    if not has_b or not has_a:
        return
    if b_oldest_price is None or b_oldest_price <= 0 or a_vol <= 0:
        return

    price_change = (b_last_price - b_oldest_price) / b_oldest_price * 100
    if price_change < user["threshold"]:
        return

    volume_change = (b_vol - a_vol) / a_vol * 100
    if volume_change < user["volume_threshold"]:
        return

    uid = user["user_id"]
    key = (uid, symbol)
    last = _cooldowns.get(key, 0.0)
    if now - last < COOLDOWN_MINUTES * 60:
        return
    _cooldowns[key] = now
    _persist_cooldown(uid, symbol, now)

    if _signal_queue is not None:
        exchange, sym = symbol.split(":", 1)
        _signal_queue.put_nowait(
            {
                "user_id": uid,
                "exchange": exchange,
                "symbol": sym,
                "price": b_last_price,
                "price_change": price_change,
                "volume_change": volume_change,
                "vol_24h": vol_24h,
                "timeframe": user["timeframe"],
            }
        )
        logger.info(
            "Signal queued for user=%d %s:%s +%.1f%%", uid, exchange, sym, price_change
        )


async def process_batch(
    tickers: list[tuple[str, float, float]], now: float
) -> None:
    """Process one WS batch: list of (symbol, price, vol_q_24h)."""
    users = await _get_users()
    window_secs = _window_seconds(users)

    for symbol, price, vol_q in tickers:
        vol_delta = 0.0
        if symbol in _last_q:
            delta = vol_q - _last_q[symbol]
            vol_delta = max(0.0, delta)
        _last_q[symbol] = vol_q
        current_24h_vol[symbol] = vol_q

        buf = price_buffer.setdefault(symbol, deque())
        buf.append((now, price, vol_delta))

        cutoff = now - window_secs
        while buf and buf[0][0] < cutoff:
            buf.popleft()

        for user in users:
            _check_and_signal(symbol, buf, user, now, vol_q)


def get_top_movers(timeframe_minutes: int = 15, n: int = 10) -> list[dict]:
    now = time.time()
    window = timeframe_minutes * 60
    results = []

    for exchange_symbol, buf in price_buffer.items():
        cutoff = now - window
        period = [(p, v) for ts, p, v in buf if ts >= cutoff]
        if len(period) < 2:
            continue
        oldest_price = period[0][0]
        newest_price = period[-1][0]
        if oldest_price <= 0:
            continue
        pct = (newest_price - oldest_price) / oldest_price * 100
        exchange, sym = exchange_symbol.split(":", 1)
        results.append(
            {
                "exchange": exchange,
                "symbol": sym,
                "price": newest_price,
                "change": pct,
                "vol_24h": current_24h_vol.get(exchange_symbol, 0.0),
            }
        )

    results.sort(key=lambda x: x["change"], reverse=True)
    return results[:n]
