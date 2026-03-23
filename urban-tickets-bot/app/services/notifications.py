from __future__ import annotations

from aiogram import Bot
from ..db.models import Payment
from ..keyboards import admin_payment_actions

async def notify_admin(
    bot: Bot,
    admin_chat_id: int,
    p: Payment,
    username: str | None,
    bank: str,
    holder: str,
    account: str,
    comment: str,
    file_type: str,
    file_id: str,
    payment_fullname: str | None = None,
    ambassador_text: str | None = None,
):
    """
    Админу отправляем ОДНО сообщение (фото/док + подпись) с кнопками Подтвердить/Отклонить.
    """
    caption = (
        "Новый платёж 💳\n"
        f"Пользователь: @{username or 'unknown'} (internal_user_id={p.user_id})\n"
        f"ФИО (билет): {payment_fullname or p.ticket_full_name or '—'}\n"
        f"Амбассадор: {ambassador_text or p.ambassador or '-'}\n"
        f"Сумма: {p.amount} ₽\n"
        f"requisites_id: {p.requisites_id}, batch #{p.batch_counter}\n"
        f"Статус: {p.status.value}\n\n"
        "Реквизиты:\n"
        f"{bank}, {holder}\n"
        f"{account}\n"
        f"Комментарий: {comment}"
    )

    if file_type == "photo":
        await bot.send_photo(
            chat_id=admin_chat_id,
            photo=file_id,
            caption=caption,
            reply_markup=admin_payment_actions(p.id),
        )
    else:
        await bot.send_document(
            chat_id=admin_chat_id,
            document=file_id,
            caption=caption,
            reply_markup=admin_payment_actions(p.id),
        )
