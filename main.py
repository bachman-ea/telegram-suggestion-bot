import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import load_config
from database import Database
from handlers import admin_router, user_router
from middlewares import MediaGroupMiddleware
from scheduler import restore_scheduled_jobs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("bot")


async def main() -> None:
    try:
        config = load_config()
    except Exception as e:
        logger.critical(f"Config error: {e}")
        return

    db = Database(config.db_path)
    scheduler = AsyncIOScheduler(timezone=config.timezone)

    bot = Bot(token=config.bot_token)
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(MediaGroupMiddleware(latency=0.6))

    dp.include_router(admin_router)
    dp.include_router(user_router)

    @dp.startup()
    async def on_startup() -> None:
        scheduler.start()
        await restore_scheduled_jobs(scheduler, bot, db, config)
        bot_info = await bot.get_me()
        logger.info(f"Bot @{bot_info.username} started")

    @dp.shutdown()
    async def on_shutdown() -> None:
        if scheduler.running:
            scheduler.shutdown()
        await bot.session.close()
        db.close()
        logger.info("Bot stopped")

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,
        db=db,
        config=config,
        scheduler=scheduler,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
