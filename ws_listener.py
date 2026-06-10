import asyncio
import logging
import time

import aiohttp
import websockets

from exchanges.base import BaseExchange
from exchanges.binance import BinanceExchange
from exchanges.bybit import BybitExchange
from analyzer import prefill_from_klines, process_batch

logger = logging.getLogger(__name__)

EXCHANGES: list[BaseExchange] = [BinanceExchange(), BybitExchange()]


async def _prefill_exchange(
    exchange: BaseExchange, pairs: set[str], candles: int = 144
) -> None:
    """Fetch 1m klines for every pair and pre-populate price_buffer."""
    sem = asyncio.Semaphore(20)
    now = time.time()
    ok = 0

    async def fetch_one(symbol: str, sess: aiohttp.ClientSession) -> None:
        nonlocal ok
        async with sem:
            try:
                data = await exchange.fetch_klines(sess, symbol, candles)
                if data:
                    prefill_from_klines(f"{exchange.name}:{symbol}", data, now)
                    ok += 1
            except Exception as exc:
                logger.debug("[%s] klines skip %s: %s", exchange.name, symbol, exc)

    logger.info("[%s] Pre-filling buffer for %d pairs…", exchange.name, len(pairs))
    async with aiohttp.ClientSession() as sess:
        await asyncio.gather(*[fetch_one(s, sess) for s in pairs])
    logger.info("[%s] Buffer prefilled: %d / %d pairs", exchange.name, ok, len(pairs))


async def _run_exchange(exchange: BaseExchange) -> None:
    pairs = await exchange.fetch_usdt_pairs()
    logger.info("[%s] Fetched %d USDT pairs", exchange.name, len(pairs))
    await _prefill_exchange(exchange, pairs)

    delay = 1
    last_refresh = time.time()

    while True:
        try:
            async with websockets.connect(
                exchange.ws_url,
                ping_interval=20,
                ping_timeout=10,
            ) as ws:
                await exchange.subscribe(ws, pairs)
                delay = 1
                logger.info("[%s] WebSocket connected", exchange.name)

                async for raw in ws:
                    # Refresh pair list once an hour
                    if time.time() - last_refresh > 3600:
                        new_pairs = await exchange.fetch_usdt_pairs()
                        if new_pairs:
                            pairs = new_pairs
                        last_refresh = time.time()

                    tickers = exchange.parse_message(raw)
                    if not tickers:
                        continue
                    now = time.time()
                    batch = [
                        (f"{exchange.name}:{sym}", price, vol_q)
                        for sym, price, vol_q in tickers
                        if sym in pairs
                    ]
                    if batch:
                        await process_batch(batch, now)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error(
                "[%s] WS error: %s — retry in %ds", exchange.name, exc, delay
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)


async def run_ws_listener() -> None:
    await asyncio.gather(*[_run_exchange(e) for e in EXCHANGES])
