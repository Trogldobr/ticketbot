from __future__ import annotations

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from ..states import TicketStates
from ..db.crud import get_or_create_user, create_payment, get_active_requisites
from ..services.rotation import handle_rotation_after_payment
from ..services.notifications import notify_admin
from ..config import Settings
from ..db.models import Requisites, Payment

# если у тебя есть клавиатура для опроса источника, импортируй; иначе просто не используем
try:
    from ..keyboards import source_survey_kb
except Exception:
    source_survey_kb = None

router = Router()

SUCCESS_TEXT = (
    "Спасибо! Мы получили данные об оплате ✅\n"
    "Ожидайте подтверждение от организатора."
)

# ───────── Шаг 1: СКРИН ─────────
@router.message(TicketStates.AwaitingScreenshot, F.photo | F.document)
async def step_screenshot(msg: Message, state: FSMContext, session: AsyncSession):
    if msg.photo:
        file_id = msg.photo[-1].file_id
        file_type = "photo"
    else:
        file_id = msg.document.file_id
        file_type = "document"

    await state.update_data(file_id=file_id, file_type=file_type)
    await msg.answer("Отлично! Теперь введите ФИО покупателя (как на билете).")
    await state.set_state(TicketStates.AwaitingFullName)

@router.message(TicketStates.AwaitingScreenshot)
async def step_screenshot_wrong(msg: Message):
    await msg.answer("Пожалуйста, пришлите скриншот в виде фото или файла (PDF/PNG/JPG).")


# ───────── Шаг 2: ФИО ─────────
@router.message(TicketStates.AwaitingFullName, F.text)
async def step_fullname(msg: Message, state: FSMContext):
    ticket_full_name = (msg.text or "").strip()
    if not ticket_full_name:
        await msg.answer("ФИО пустое. Введите ФИО полностью.")
        return

    await state.update_data(ticket_full_name=ticket_full_name)
    await msg.answer("Кто вас пригласил? Укажите @username или имя.\nЕсли никого — напишите «-».")
    await state.set_state(TicketStates.AwaitingAmbassador)

@router.message(TicketStates.AwaitingFullName)
async def step_fullname_wrong(msg: Message):
    await msg.answer("Пожалуйста, отправьте ФИО текстом.")


# ───────── Шаг 3: АМБАССАДОР ─────────
@router.message(TicketStates.AwaitingAmbassador, F.text)
async def step_ambassador(msg: Message, state: FSMContext, session: AsyncSession, settings: Settings, bot):
    data = await state.get_data()
    file_id = data.get("file_id")
    file_type = data.get("file_type")
    ticket_full_name = data.get("ticket_full_name")
    expected_req_id = data.get("expected_requisites_id")

    ambassador = (msg.text or "").strip() or "-"
    if ambassador == "":
        ambassador = "-"

    # актуализируем профильное имя (НЕ билетное)
    profile_fullname = " ".join(filter(None, [msg.from_user.first_name, msg.from_user.last_name])) or None
    user = await get_or_create_user(session, msg.from_user.id, msg.from_user.username, profile_fullname)

    # страхуемся, если контекст реквизитов потерян
    req_id_for_payment = expected_req_id
    if req_id_for_payment is None:
        active = await get_active_requisites(session)
        req_id_for_payment = active.id if active else None

    if not (file_id and file_type and ticket_full_name and req_id_for_payment):
        await msg.answer("Техническая ошибка: не хватает данных. Начните заново: «Купить билет».")
        await state.set_state(TicketStates.Idle)
        return

    # инкремент и возможная ротация
    batch_counter = await handle_rotation_after_payment(session, req_id_for_payment)

    # сумма из реквизитов (поддержка кастомной цены)
    reqs: Requisites | None = await session.get(Requisites, req_id_for_payment)
    amount = reqs.price if reqs else settings.price_rub

    # создаём платеж (важно: create_payment должен принимать ticket_full_name и ambassador)
    p: Payment = await create_payment(
        session=session,
        user_id=user.id,
        requisites_id=req_id_for_payment,
        amount=amount,
        file_id=file_id,
        file_type=file_type,
        batch_counter=batch_counter,
        ticket_full_name=ticket_full_name,
        ambassador=ambassador,
    )
    await session.commit()

    # пользователю — подтверждение получения + (опционально) опрос «источник»
    await msg.answer(SUCCESS_TEXT)
    if source_survey_kb:
        try:
            await msg.answer("Откуда вы узнали о мероприятии?", reply_markup=source_survey_kb(p.id))
        except Exception:
            pass

    # админу — ОДНО сообщение с вложением + кнопки
    # (notify_admin сам подставит все нужные поля)
    from_username = msg.from_user.username
    await notify_admin(
        bot=bot,
        admin_chat_id=settings.admin_chat_id,
        p=p,
        username=from_username,
        bank=reqs.bank if reqs else "",
        holder=reqs.holder if reqs else "",
        account=reqs.account if reqs else "",
        comment=reqs.comment if reqs else "",
        file_type=file_type,
        file_id=file_id,
        payment_fullname=ticket_full_name,
        ambassador_text=ambassador,
    )

    await state.set_state(TicketStates.Idle)

@router.message(TicketStates.AwaitingAmbassador)
async def step_ambassador_wrong(msg: Message):
    await msg.answer("Пожалуйста, отправьте имя амбассадора текстом (или «-»).")
