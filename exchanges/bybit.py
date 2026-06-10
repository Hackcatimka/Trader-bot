import json

import aiohttp

from .base import BaseExchange

_REST = "https://api.bybit.com"


class BybitExchange(BaseExchange):
    name = "BYBIT"
    ws_url = "wss://stream.bybit.com/v5/public/spot"

    async def fetch_usdt_pairs(self) -> set[str]:
        url = f"{_REST}/v5/market/instruments-info"
        params: dict = {"category": "spot", "limit": 1000}
        pairs: set[str] = set()
        async with aiohttp.ClientSession() as s:
            while True:
                async with s.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as r:
                    data = await r.json()
                result = data.get("result", {})
                for item in result.get("list", []):
                    if item.get("quoteCoin") == "USDT" and item.get("status") == "Trading":
                        pairs.add(item["symbol"])
                cursor = result.get("nextPageCursor", "")
                if not cursor:
                    break
                params["cursor"] = cursor
        return pairs

    async def subscribe(self, ws, pairs: set[str]) -> None:
        args = [f"tickers.{sym}" for sym in pairs]
        for i in range(0, len(args), 100):
            chunk = args[i : i + 100]
            await ws.send(json.dumps({"op": "subscribe", "args": chunk}))

    def parse_message(self, raw: str) -> list[tuple[str, float, float]]:
        try:
            msg = json.loads(raw)
            topic = msg.get("topic", "")
            if not topic.startswith("tickers."):
                return []
            data = msg.get("data", {})
            symbol = data.get("symbol", "")
            price_str = data.get("lastPrice", "")
            vol_str = data.get("turnover24h", "")
            # delta messages may omit fields — skip incomplete ones
            if not (symbol and price_str and vol_str):
                return []
            price = float(price_str)
            if price <= 0:
                return []
            return [(symbol, price, float(vol_str))]
        except Exception:
            return []

    async def fetch_klines(
        self,
        session: aiohttp.ClientSession,
        symbol: str,
        limit: int,
    ) -> list[tuple[float, float, float]]:
        url = f"{_REST}/v5/market/kline"
        params = {"category": "spot", "symbol": symbol, "interval": "1", "limit": limit}
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
            data = await r.json()
        items = data.get("result", {}).get("list", [])
        if not items:
            return []
        # Bybit returns newest-first → reverse to ascending
        # Each item: [startTime_ms, open, high, low, close, base_vol, quote_vol]
        result = []
        for k in reversed(items):
            close_time_s = (float(k[0]) + 60_000) / 1000  # start + 1 min
            result.append((close_time_s, float(k[4]), float(k[6])))
        return result
