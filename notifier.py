import asyncio
import logging
import random

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

logger = logging.getLogger(__name__)

_HEADERS = [
    "🚀🚀🚀 <b>ОЙ ОЙ ОЙ стой стой стой!!</b>",
    "👀 <b>ЭÉÉÉ, ты видел это?!</b>",
    "🔥🔥🔥 <b>ЧТО-ТО ПРОИСХОДИТ!</b>",
    "⚡️ <b>АЛЛО, ЗЕМЛЯ, ТУТ ДВИЖУХА!</b>",
    "🤯 <b>БРАТАН, СМОТРИ СЮДА!</b>",
    "💣 <b>ВНИМАНИЕ, ВНИМАНИЕ!</b>",
]

_FOOTERS = [
    "ну ты сам решай конечно... я просто говорю 🤷‍♀️",
    "дальше сам, я своё дело сделал 😇",
    "это не сигнал, это просто наблюдение... или нет? 👁",
    "мне заплатили только за то чтобы сообщить, остальное на тебе 🫡",
    "хочешь — входи, хочешь — нет, я не твоя мама 🙃",
    "ладно, не буду мешать. удачи там 🍀",
]


def _format_signal(sig: dict) -> str:
    sym = sig["symbol"].replace("USDT", "/USDT")
    exchange = sig["exchange"].capitalize()
    price = sig["price"]
    price_change = sig["price_change"]
    volume_change = sig["volume_change"]
    vol_24h = sig["vol_24h"]
    tf = sig["timeframe"]

    if vol_24h >= 1e9:
        vol_str = f"${vol_24h / 1e9:.2f}B"
    elif vol_24h >= 1e6:
        vol_str = f"${vol_24h / 1e6:.0f}M"
    else:
        vol_str = f"${vol_24h:,.0f}"

    header = random.choice(_HEADERS)
    footer = random.choice(_FOOTERS)

    return (
        f"{header}\n\n"
        f"монета:    <b>{sym}</b>  <i>[{exchange}]</i> 👀\n"
        f"цена:      <b>${price:.6g}</b>  (<b>+{price_change:.1f}%</b> за {tf} мин) 📈\n"
        f"объём:     <b>+{volume_change:.0f}%</b> к предыдущим {tf} мин 💥\n"
        f"объём 24h: <b>{vol_str}</b> 💰\n\n"
        f"{footer}"
    )


async def run_notifier(bot: Bot, queue: asyncio.Queue) -> None:
    while True:
        sig = await queue.get()
        try:
            await bot.send_message(sig["user_id"], _format_signal(sig))
        except TelegramForbiddenError:
            logger.info("User %d blocked the bot — skipping", sig["user_id"])
        except TelegramBadRequest as exc:
            logger.warning("Bad request for user %d: %s", sig["user_id"], exc)
        except Exception as exc:
            logger.error("Failed to notify user %d: %s", sig["user_id"], exc)
        finally:
            queue.task_done()
