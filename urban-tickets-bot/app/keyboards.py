from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def start_menu(price: int | None) -> InlineKeyboardMarkup:
    # если цены нет (нет активных реквизитов) — просто «Купить билет»
    label = f"Купить билет — {price} ₽" if price else "Купить билет"
    kb = [
        [InlineKeyboardButton(text=label, callback_data="buy_2500")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)

def buy_menu() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="Оплатил", callback_data="paid_clicked")],
        [InlineKeyboardButton(text="Назад", callback_data="back_to_menu")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


def admin_payment_actions(payment_id: int) -> InlineKeyboardMarkup:
    kb = [[
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm:{payment_id}"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject:{payment_id}"),
    ]]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# Опрос «Откуда узнали о мероприятии» (inline-кнопки)
# callback_data вида: src:{payment_id}:{code}
SOURCE_OPTIONS = [
    ("Друг/знакомый", "friend"),
    ("Амбассадор", "ambassador"),
    ("Instagram", "ig"),
    ("Telegram-канал", "tg"),
    ("Другое", "other"),
    ("-", "dash"),
]

def source_survey_kb(payment_id: int) -> InlineKeyboardMarkup:
    rows = []
    row = []
    for idx, (label, code) in enumerate(SOURCE_OPTIONS, start=1):
        row.append(InlineKeyboardButton(text=label, callback_data=f"src:{payment_id}:{code}"))
        if idx % 2 == 0:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)
