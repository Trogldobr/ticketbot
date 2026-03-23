import asyncio
import logging
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage

from sqlalchemy.ext.asyncio import AsyncSession
from .db.base import SessionLocal, healthcheck
from .config import load_settings, Settings
from .middlewares.throttling import SimpleThrottleMiddleware
from .handlers import start as start_handlers
from .handlers import callbacks as cb_handlers
from .handlers import payments as payments_handlers
from .handlers import admin as admin_handlers

from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


from typing import Callable, Dict, Any, Awaitable


class DBSessionMiddleware(BaseMiddleware):
    async def __call__(self, handler: Callable, event, data: Dict[str, Any]) -> Any:
        async with SessionLocal() as session:
            data["session"] = session  # type: AsyncSession
            res = await handler(event, data)
            return res

class SettingsMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings):
        self.settings = settings
        super().__init__()
    async def __call__(self, handler: Callable, event, data: Dict[str, Any]) -> Any:
        data["settings"] = self.settings
        return await handler(event, data)

async def main():
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    settings = load_settings()

    await healthcheck()

    if settings.redis_url:
        storage = RedisStorage.from_url(settings.redis_url)
    else:
        storage = MemoryStorage()

    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=storage)

    dp.include_router(start_handlers.router)
    dp.include_router(cb_handlers.router)
    dp.include_router(payments_handlers.router)
    dp.include_router(admin_handlers.router)

    dp.callback_query.middleware(SimpleThrottleMiddleware(interval=2.0))
    dp.message.middleware(DBSessionMiddleware())
    dp.callback_query.middleware(DBSessionMiddleware())
    dp.message.middleware(SettingsMiddleware(settings))
    dp.callback_query.middleware(SettingsMiddleware(settings))

    logging.info("Urban Tickets bot started")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

if __name__ == "__main__":
    asyncio.run(main())
