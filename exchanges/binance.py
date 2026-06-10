import json

import aiohttp

from .base import BaseExchange

_REST = "https://api.binance.com"


class BinanceExchange(BaseExchange):
    name = "BINANCE"
    ws_url = "wss://stream.binance.com:9443/ws/!miniTicker@arr"

    async def fetch_usdt_pairs(self) -> set[str]:
        url = f"{_REST}/api/v3/exchangeInfo"
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=30)) as r:
                data = await r.json()
        return {
            sym["symbol"]
            for sym in data.get("symbols", [])
            if sym.get("quoteAsset") == "USDT"
            and sym.get("status") == "TRADING"
            and sym.get("isSpotTradingAllowed", False)
        }

    async def subscribe(self, ws, pairs: set[str]) -> None:
        pass  # !miniTicker@arr pushes all tickers automatically

    def parse_message(self, raw: str) -> list[tuple[str, float, float]]:
        try:
            tickers = json.loads(raw)
            result = []
            for t in tickers:
                sym = t.get("s", "")
                price_str = t.get("c", "")
                vol_str = t.get("q", "")
                if not (sym and price_str and vol_str):
                    continue
                price = float(price_str)
                if price > 0:
                    result.append((sym, price, float(vol_str)))
            return result
        except Exception:
            return []

    async def fetch_klines(
        self,
        session: aiohttp.ClientSession,
        symbol: str,
        limit: int,
    ) -> list[tuple[float, float, float]]:
        url = f"{_REST}/api/v3/klines"
        params = {"symbol": symbol, "interval": "1m", "limit": limit}
        async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as r:
            data = await r.json()
        if not isinstance(data, list):
            return []
        # Binance: ascending, index 6 = close_time_ms, 4 = close, 7 = quote_vol
        return [(float(k[6]) / 1000, float(k[4]), float(k[7])) for k in data]
