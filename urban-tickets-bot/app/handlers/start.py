from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.crud import get_active_requisites, get_or_create_user
from ..keyboards import start_menu

router = Router()

@router.message(CommandStart())
async def cmd_start(msg: Message, session: AsyncSession):
    # создадим/обновим пользователя (без привязки имени билета)
    full_name = " ".join(filter(None, [msg.from_user.first_name, msg.from_user.last_name])) or None
    await get_or_create_user(session, msg.from_user.id, msg.from_user.username, full_name)

    # найдём активные реквизиты, возьмём цену для кнопки
    req = await get_active_requisites(session)
    price = req.price if req else None

    await msg.answer(
        "Привет! Это Urban Tickets.\nЗдесь можно купить билет на ближайшее мероприятие.",
        reply_markup=start_menu(price)
    )
