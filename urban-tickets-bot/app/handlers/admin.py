from __future__ import annotations

import asyncio
from io import BytesIO
from datetime import timezone

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import Command, CommandObject
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from ..config import Settings
from ..db.crud import (
    stats as stats_query,
    rotate_to_next,
    list_requisites,
    add_requisites,
    set_active_requisites,
    set_payment_status,
    set_payment_ambassador,
)
from ..db.models import PaymentStatus, Payment, User, Requisites

router = Router()

def is_admin(user_id: int, settings: Settings) -> bool:
    return user_id in settings.admins or (settings.admin_chat_id == user_id)

# ---------- БАЗОВЫЕ КОМАНДЫ ----------

@router.message(Command("stats"))
async def cmd_stats(msg: Message, session: AsyncSession, settings: Settings):
    if not is_admin(msg.from_user.id, settings):
        return
    s = await stats_query(session)
    lines = [f"📊 Статистика:", f"Всего оплат: {s['total']}"]
    if s["active_id"]:
        lines.append(
            f"Активные реквизиты: id={s['active_id']}, usage_count={s['active_usage']}, "
            f"осталось до ротации: {s['remain_to_rotate']}"
        )
    lines.append("По requisites_id:")
    for rid, cnt in s["per_requisites"].items():
        lines.append(f"  - {rid}: {cnt}")
    await msg.answer("\n".join(lines))

@router.message(Command("listreq"))
async def cmd_listreq(msg: Message, session: AsyncSession, settings: Settings):
    if not is_admin(msg.from_user.id, settings):
        return
    allr = await list_requisites(session)
    if not allr:
        await msg.answer("Реквизиты не найдены.")
        return

    lines = []
    for r in allr:
        price = getattr(r, "price", None)  # чтобы не падать до применения миграции
        price_part = f" | price={price} ₽" if price is not None else ""
        lines.append(
            f"[id={r.id}] {'✅' if r.active else '  '} #{r.order_idx} | usage={r.usage_count}{price_part}\n"
            f"{r.bank} | {r.holder}\n{r.account}\nкомментарий: {r.comment}\n"
        )
    await msg.answer("\n".join(lines))


@router.message(Command("rotate"))
async def cmd_rotate(msg: Message, session: AsyncSession, settings: Settings):
    if not is_admin(msg.from_user.id, settings):
        return
    next_r = await rotate_to_next(session)
    await session.commit()
    if next_r:
        await msg.answer(f"Переключено на requisites id={next_r.id} (#order={next_r.order_idx}). usage_count=0")
    else:
        await msg.answer("Нет активных реквизитов для переключения.")

@router.message(Command("setactive"))
async def cmd_setactive(msg: Message, session: AsyncSession, settings: Settings):
    if not is_admin(msg.from_user.id, settings):
        return
    parts = msg.text.strip().split()
    if len(parts) != 2 or not parts[1].isdigit():
        await msg.answer("Использование: /setactive <id>")
        return
    rid = int(parts[1])
    await set_active_requisites(session, rid)
    await session.commit()
    await msg.answer(f"Активированы реквизиты id={rid} (usage_count сброшен).")

@router.message(Command("addreq"))
async def cmd_addreq(msg: Message, session: AsyncSession, settings: Settings):
    if not is_admin(msg.from_user.id, settings):
        return
    try:
        payload = msg.text.split(" ", 1)[1]
        parts = [x.strip() for x in payload.split(";")]
        if len(parts) != 6:
            raise ValueError
        bank, holder, account, comment, order_idx_str, price_str = parts
        order_idx = int(order_idx_str)
        price = int(price_str)
    except Exception:
        await msg.answer("Использование:\n/addreq bank;holder;account;comment;order_idx;price\n"
                         "Например:\n/addreq Тинькофф;Иванов Иван;5536 **** **** 1234;Urban_2500;1;2500")
        return

    r = await add_requisites(session, bank, holder, account, comment, order_idx, price)
    await session.commit()
    await msg.answer(f"Добавлено: id={r.id}, order_idx={r.order_idx}, price={r.price} ₽")

# ---------- ОЧИСТКА/СПИСОК/ЭКСПОРТ ----------

@router.message(Command("clear_payments"))
async def cmd_clear_payments(msg: Message, session: AsyncSession, settings: Settings):
    if not is_admin(msg.from_user.id, settings):
        return
    await session.execute(text("TRUNCATE TABLE payments RESTART IDENTITY CASCADE;"))
    await session.commit()
    await msg.answer("Таблица payments очищена и счётчик ID сброшен.")

@router.message(Command("payments"))
async def cmd_payments(msg: Message, session: AsyncSession, settings: Settings, command: CommandObject):
    if not is_admin(msg.from_user.id, settings):
        return
    try:
        limit = int((command.args or "20").strip())
    except Exception:
        limit = 20
    limit = max(1, min(limit, 100))

    q = (
        select(Payment, User, Requisites)
        .join(User, User.id == Payment.user_id)
        .join(Requisites, Requisites.id == Payment.requisites_id)
        .order_by(Payment.id.desc())
        .limit(limit)
    )
    res = await session.execute(q)
    rows = res.all()

    if not rows:
        await msg.answer("Платежей пока нет.")
        return

    lines = ["Последние платежи:"]
    for p, u, r in rows:
        lines.append(
            f"#{p.id} | {p.created_at:%Y-%m-%d %H:%M} | {p.amount} ₽ | {p.status.value}\n"
            f"  user: @{u.username or '—'} (tg_id={u.tg_id})\n"
            f"  ФИО (билет): {p.ticket_full_name or '—'} | Амбассадор: {p.ambassador or '—'}\n"
            f"  req_id={r.id} batch={p.batch_counter} type={p.file_type}\n"
            f"  bank={r.bank} holder={r.holder}\n"
        )

    text_out = "\n".join(lines)
    for i in range(0, len(text_out), 3900):
        await msg.answer(text_out[i:i+3900])

@router.message(Command("export_excel"))
async def cmd_export_excel(msg: Message, session: AsyncSession, settings: Settings):
    if not is_admin(msg.from_user.id, settings):
        return

    q = (
        select(Payment, User, Requisites)
        .join(User, User.id == Payment.user_id)
        .join(Requisites, Requisites.id == Payment.requisites_id)
        .order_by(Payment.id.asc())
    )
    res = await session.execute(q)
    rows = res.all()

    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Payments"

    headers = [
        "payment_id", "created_at", "amount", "file_type", "batch_counter", "status",
        "ticket_full_name", "ambassador",
        "user_id", "user_tg_id", "username", "user_full_name",
        "requisites_id", "bank", "holder", "account", "comment", "req_price",
    ]
    ws.append(headers)

    def to_excel_dt(dt):
        if dt is None:
            return None
        return dt.astimezone(timezone.utc).replace(tzinfo=None)

    for p, u, r in rows:
        ws.append([
            p.id,
            to_excel_dt(p.created_at),
            p.amount,
            p.file_type,
            p.batch_counter,
            p.status.value,
            p.ticket_full_name,
            p.ambassador,
            u.id,
            u.tg_id,
            u.username,
            u.full_name,
            r.id,
            r.bank,
            r.holder,
            r.account,
            r.comment,
            r.price,
        ])

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    await msg.answer_document(
        BufferedInputFile(bio.read(), filename="payments_export.xlsx"),
        caption=f"Экспорт платежей: {len(rows)} записей",
    )

# ---------- РАССЫЛКА ВСЕМ ПОЛЬЗОВАТЕЛЯМ ----------

@router.message(Command("broadcast"))
async def cmd_broadcast(msg: Message, session: AsyncSession, settings: Settings, command: CommandObject, bot):
    """
    /broadcast <текст>
    Отправляет сообщение всем пользователям из таблицы users.
    """
    if not is_admin(msg.from_user.id, settings):
        return
    text = (command.args or "").strip()
    if not text:
        await msg.answer("Использование: /broadcast текст сообщения")
        return

    res = await session.execute(select(User.tg_id))
    tg_ids = [row[0] for row in res.all()]
    ok = 0; fail = 0
    for uid in tg_ids:
        try:
            await bot.send_message(uid, text)
            ok += 1
            await asyncio.sleep(0.05)  # чуть бережём лимиты
        except Exception:
            fail += 1
    await msg.answer(f"✅ Разослано: {ok}, ❌ ошибок: {fail}")

# ---------- КОЛБЭКИ ИЗ АДМИН-УВЕДОМЛЕНИЙ ----------

@router.callback_query(F.data.startswith("admin_confirm:"))
async def cb_confirm(cb: CallbackQuery, session: AsyncSession, settings: Settings, bot):
    if not is_admin(cb.from_user.id, settings):
        await cb.answer()
        return

    pid = int(cb.data.split(":")[1])
    await set_payment_status(session, pid, PaymentStatus.confirmed)

    # Уведомим пользователя об успешном подтверждении
    res = await session.execute(
        select(Payment, User).join(User, User.id == Payment.user_id).where(Payment.id == pid)
    )
    pair = res.one_or_none()
    await session.commit()

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("Подтверждено ✅")

    if pair:
        p, u = pair
        try:
            await bot.send_message(
                u.tg_id,
                "✅ Оплата подтверждена!\n"
                "Спасибо! Ждём вас на Urban 🎉"
            )
        except Exception:
            pass

@router.callback_query(F.data.startswith("admin_reject:"))
async def cb_reject(cb: CallbackQuery, session: AsyncSession, settings: Settings, bot):
    if not is_admin(cb.from_user.id, settings):
        await cb.answer()
        return

    pid = int(cb.data.split(":")[1])
    await set_payment_status(session, pid, PaymentStatus.rejected)

    # Уведомим пользователя об отклонении
    res = await session.execute(
        select(Payment, User).join(User, User.id == Payment.user_id).where(Payment.id == pid)
    )
    pair = res.one_or_none()
    await session.commit()

    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("Отклонено ❌")

    if pair:
        p, u = pair
        try:
            await bot.send_message(
                u.tg_id,
                "⚠️ Оплата не подтверждена.\n"
                "Если это ошибка — напишите, пожалуйста, организатору и пришлите корректный скрин."
            )
        except Exception:
            pass

# ---------- КОЛБЭК «источник» (опрос) ----------

@router.callback_query(F.data.startswith("src:"))
async def cb_source(cb: CallbackQuery, session: AsyncSession, settings: Settings):
    if not cb.data:
        await cb.answer()
        return
    try:
        _, pid_str, code = cb.data.split(":")
        pid = int(pid_str)
    except Exception:
        await cb.answer()
        return

    # Маппинг в читаемый текст
    mapping = {
        "friend": "Друг/знакомый",
        "ambassador": "Амбассадор",
        "ig": "Instagram",
        "tg": "Telegram-канал",
        "other": "Другое",
        "dash": "-",
    }
    text_value = mapping.get(code, code)

    await set_payment_ambassador(session, pid, text_value)
    await session.commit()
    await cb.message.edit_reply_markup(reply_markup=None)
    await cb.answer("Спасибо!")
