from abc import ABC, abstractmethod

import aiohttp


class BaseExchange(ABC):
    name: str    # "BINANCE", "BYBIT", …
    ws_url: str  # WebSocket endpoint

    @abstractmethod
    async def fetch_usdt_pairs(self) -> set[str]:
        """Return set of tradeable USDT spot pair symbols."""
        ...

    @abstractmethod
    async def subscribe(self, ws, pairs: set[str]) -> None:
        """Send subscription message(s) right after WS connects."""
        ...

    @abstractmethod
    def parse_message(self, raw: str) -> list[tuple[str, float, float]]:
        """Parse one raw WS message → [(symbol, price, vol_q_24h)]."""
        ...

    @abstractmethod
    async def fetch_klines(
        self,
        session: aiohttp.ClientSession,
        symbol: str,
        limit: int,
    ) -> list[tuple[float, float, float]]:
        """Fetch 1-min klines → [(close_time_seconds, close_price, quote_vol)]
        sorted ascending (oldest first)."""
        ...
