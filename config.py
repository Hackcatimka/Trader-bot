import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]
DB_PATH: str = os.getenv("DB_PATH", "bot.db")

BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/!miniTicker@arr"
BINANCE_REST_URL = "https://api.binance.com"

DEFAULT_TIMEFRAME = 15
DEFAULT_THRESHOLD = 10.0
DEFAULT_VOLUME_THRESHOLD = 50.0
DEFAULT_MIN_VOLUME_USD = 1_000_000.0
COOLDOWN_MINUTES = 30
