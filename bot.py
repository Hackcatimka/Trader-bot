import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from database import init_db
from handlers import router
from analyzer import init_signal_queue, init_cooldowns
from notifier import run_notifier
from ws_listener import run_ws_listener

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    await init_db()
    await init_cooldowns()
    logger.info("Database ready")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    signal_queue: asyncio.Queue = asyncio.Queue()
    init_signal_queue(signal_queue)

    logger.info("Starting bot, WS listener, and notifier")
    await asyncio.gather(
        dp.start_polling(bot, allowed_updates=["message"]),
        run_ws_listener(),
        run_notifier(bot, signal_queue),
    )


if __name__ == "__main__":
    asyncio.run(main())
