import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.session.aiohttp import AiohttpSession
from config import Config
from handlers import start, clients, connection, server_stats, requests, monitoring

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

async def main():
    config = Config()
    proxy = os.getenv("HTTPS_PROXY")
    session = AiohttpSession(proxy=proxy) if proxy else None
    bot = Bot(token=config.BOT_TOKEN, session=session) if session else Bot(token=config.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(requests.router)
    dp.include_router(monitoring.router)
    dp.include_router(start.router)
    dp.include_router(clients.router)
    dp.include_router(connection.router)
    dp.include_router(server_stats.router)
    logger.info("Bot started")
    await dp.start_polling(bot, config=config)

if __name__ == "__main__":
    asyncio.run(main())
