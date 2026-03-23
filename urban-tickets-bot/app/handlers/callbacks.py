import asyncio
from contextlib import suppress

from aiogram import Router, F
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.crud import get_active_requisites, get_or_create_user
from ..keyboards import start_menu, buy_menu
from ..states import TicketStates
from ..config import Settings

router = Router()

# <<< Настройка таймера удаления сообщения с реквизитами (в секундах) >>>
PAYMENT_EXPIRE_SECONDS = 600  # 10 минут

def format_requisites(bank: str, holder: str, account: str, comment: str, price: int) -> str:
    # 2500 -> "2 500"
    price_text = f"{price:,} ₽".replace(",", " ")
    return (
        f"💳 Реквизиты для перевода ({price_text}):\n"
        "```\n"
        f"Банк: {bank}\n"
        f"Получатель: {holder}\n"
        f"Номер карты/счёта: {account}\n"
        f"Комментарий к платежу: {comment}\n"
        "```"
    )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu(cb: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Возврат в меню; кнопка «Купить…» показывает актуальную цену из активных реквизитов."""
    await state.set_state(TicketStates.Idle)
    req = await get_active_requisites(session)
    price = req.price if req else None

    await cb.message.edit_text(
        "Привет! Это Urban Tickets.\nЗдесь можно купить билет на ближайшее мероприятие Urban.",
        reply_markup=start_menu(price)  # убедись, что start_menu умеет принимать price: Optional[int]
    )
    await cb.answer()


@router.callback_query(F.data == "buy_2500")
async def buy_2500(cb: CallbackQuery, state: FSMContext, session: AsyncSession, settings: Settings):
    """Показываем реквизиты + запоминаем их id в FSM и переводим в ожидание СКРИНА."""
    # сохраним профильное имя пользователя (НЕ имя на билете)
    profile_fullname = " ".join(filter(None, [cb.from_user.first_name, cb.from_user.last_name])) or None
    await get_or_create_user(session, cb.from_user.id, cb.from_user.username, profile_fullname)

    req = await get_active_requisites(session)
    if not req:
        await cb.message.answer("Сейчас нет активных реквизитов. Попробуйте позже.")
        await cb.answer()
        return

    await state.update_data(expected_requisites_id=req.id)

    text = format_requisites(req.bank, req.holder, req.account, req.comment, req.price)
    await cb.message.edit_text(text, reply_markup=buy_menu(), parse_mode="Markdown")

    # ждём скрин
    await state.set_state(TicketStates.AwaitingScreenshot)

    # запустим авто-удаление сообщения с реквизитами, если скрин не пришёл
    chat_id = cb.message.chat.id
    req_msg_id = cb.message.message_id

    async def expiry_watch():
        await asyncio.sleep(PAYMENT_EXPIRE_SECONDS)
        current = await state.get_state()
        if current == TicketStates.AwaitingScreenshot.state:
            with suppress(TelegramBadRequest):
                await cb.message.bot.delete_message(chat_id, req_msg_id)
            await cb.message.answer(
                "⏰ Время на оплату истекло. Реквизиты могли поменяться.\n"
                "Нажмите «Купить билет» ещё раз, чтобы получить актуальные реквизиты."
            )
            await state.set_state(TicketStates.Idle)

    asyncio.create_task(expiry_watch())
    await cb.answer()


@router.callback_query(F.data == "paid_clicked")
async def paid_clicked(cb: CallbackQuery, state: FSMContext, settings: Settings):
    """Подсказка пользователю перед отправкой скрина."""
    await state.set_state(TicketStates.AwaitingScreenshot)
    await cb.message.answer(
        "Пришлите скриншот успешного платежа.\n"
        "Образец ниже: обратите внимание на сумму, дату/время и последние цифры карты."
    )
    try:
        example = FSInputFile(settings.assets_example_path)
        await cb.message.answer_photo(example)
    except Exception:
        pass
    await cb.answer()
