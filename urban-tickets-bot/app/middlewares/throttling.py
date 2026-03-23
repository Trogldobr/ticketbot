import time
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery
from typing import Callable, Dict, Any, Awaitable

class SimpleThrottleMiddleware(BaseMiddleware):
    """Простейший троттлинг callback'ов: один клик в 2 секунды."""
    def __init__(self, interval: float = 2.0):
        super().__init__()
        self.interval = interval
        self.last_click: Dict[int, float] = {}

    async def __call__(self, handler: Callable[[CallbackQuery, Dict[str, Any]], Awaitable[Any]], event: CallbackQuery, data: Dict[str, Any]) -> Any:
        user_id = event.from_user.id if event.from_user else 0
        now = time.monotonic()
        prev = self.last_click.get(user_id, 0.0)
        if now - prev < self.interval:
            return
        self.last_click[user_id] = now
        return await handler(event, data)
