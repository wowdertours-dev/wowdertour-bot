from aiogram import Router
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import ADMIN_IDS
from keyboards.admin_menu import admin_menu
from database.db import (
    get_all_bookings,
    get_booking_by_id,
    get_bookings_stats,
    update_booking_status,
)

router = Router()


# ============================================================
# ПРОВЕРКА АДМИНА
# ============================================================

def is_admin(user_id: int):
    return user_id in ADMIN_IDS


# ============================================================
# КНОПКИ КАРТОЧКИ ЗАЯВКИ
# ============================================================

def booking_keyboard(booking_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆕 Новая",
                    callback_data=f"status:{booking_id}:Новая",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟡 Связались",
                    callback_data=f"status:{booking_id}:Связались",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💸 Предоплата",
                    callback_data=f"status:{booking_id}:Предоплата",
                )
            ],
            [
                InlineKeyboardButton(
                    text="💰 Оплачено",
                    callback_data=f"status:{booking_id}:Оплачено",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔴 Отмена",
                    callback_data=f"status:{booking_id}:Отмена",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ К заявкам",
                    callback_data="admin_bookings",
                )
            ],
        ]
    )


# ============================================================
# /admin
# ============================================================

@router.message(Command("admin"))
async def admin_panel(message: Message):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "🛠 <b>Панель администратора WowderTour</b>",
        reply_markup=admin_menu,
        parse_mode="HTML",
    )


# ============================================================
# СПИСОК ЗАЯВОК
# ============================================================

@router.callback_query(lambda c: c.data == "admin_bookings")
async def admin_bookings(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        return

    bookings = get_all_bookings()

    if not bookings:
        await callback.message.edit_text(
            "📭 <b>Пока нет заявок.</b>",
            reply_markup=admin_menu,
            parse_mode="HTML",
        )
        await callback.answer()
        return

    keyboard = []

    for booking in bookings:

        (
            booking_id,
            telegram_id,
            username,
            full_name,
            phone,
            tour,
            tour_key,
            tour_date,
            people,
            comment,
            status,
            created_at,
        ) = booking

        icon = {
            "Новая": "🆕",
            "Связались": "🟡",
            "Предоплата": "💸",
            "Оплачено": "💰",
            "Отмена": "🔴",
        }.get(status, "⚪")

        if "Кировск" in tour:
            tour_name = "🏂 Кировск"
        elif "Шерегеш" in tour:
            tour_name = "🔥 Шерегеш"
        elif "Вейк" in tour:
            tour_name = "🏄 Вейк"
        else:
            tour_name = "🛹 Скейт"

        keyboard.append([
            InlineKeyboardButton(
                text=f"{icon} #{booking_id} • {full_name} • {tour_name}",
                callback_data=f"booking:{booking_id}",
            )
        ])

    keyboard.append([
        InlineKeyboardButton(
            text="⬅️ Админ-панель",
            callback_data="admin_home",
        )
    ])

    await callback.message.edit_text(
        "📋 <b>Заявки WowderTour</b>\n\n"
        "Выбери заявку:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# КАРТОЧКА ЗАЯВКИ
# ============================================================

@router.callback_query(lambda c: c.data.startswith("booking:"))
async def booking_card(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        return

    booking_id = int(callback.data.split(":")[1])

    booking = get_booking_by_id(booking_id)

    if not booking:
        await callback.answer("Заявка не найдена")
        return

    (
        booking_id,
        telegram_id,
        username,
        full_name,
        phone,
        tour,
        tour_key,
        tour_date,
        people,
        comment,
        status,
        created_at,
    ) = booking

    icon = {
        "Новая": "🆕",
        "Связались": "🟡",
        "Предоплата": "💸",
        "Оплачено": "💰",
        "Отмена": "🔴",
    }.get(status, "⚪")

    username_text = f"@{username}" if username else "не указан"

    text = (
        f"📋 <b>Заявка #{booking_id}</b>\n\n"

        f"👤 <b>{full_name}</b>\n"
        f"📱 {phone}\n"
        f"📲 {username_text}\n"
        f"🆔 <code>{telegram_id}</code>\n\n"

        f"🏂 <b>{tour}</b>\n"
        f"📅 {tour_date}\n"
        f"👥 {people} чел.\n\n"

        f"💬 <b>Комментарий</b>\n"
        f"{comment}\n\n"

        f"{icon} <b>Статус:</b> {status}\n"
        f"🕐 {created_at}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=booking_keyboard(booking_id),
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# СМЕНА СТАТУСА
# ============================================================

@router.callback_query(lambda c: c.data.startswith("status:"))
async def change_status(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        return

    _, booking_id, status = callback.data.split(":", 2)

    update_booking_status(
        int(booking_id),
        status,
    )

    booking = get_booking_by_id(int(booking_id))

    (
        booking_id,
        telegram_id,
        username,
        full_name,
        phone,
        tour,
        tour_key,
        tour_date,
        people,
        comment,
        status,
        created_at,
    ) = booking

    icon = {
        "Новая": "🆕",
        "Связались": "🟡",
        "Предоплата": "💸",
        "Оплачено": "💰",
        "Отмена": "🔴",
    }.get(status, "⚪")

    username_text = f"@{username}" if username else "не указан"

    text = (
        f"📋 <b>Заявка #{booking_id}</b>\n\n"

        f"👤 <b>{full_name}</b>\n"
        f"📱 {phone}\n"
        f"📲 {username_text}\n"
        f"🆔 <code>{telegram_id}</code>\n\n"

        f"🏂 <b>{tour}</b>\n"
        f"📅 {tour_date}\n"
        f"👥 {people} чел.\n\n"

        f"💬 <b>Комментарий</b>\n"
        f"{comment}\n\n"

        f"{icon} <b>Статус:</b> {status}\n"
        f"🕐 {created_at}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=booking_keyboard(booking_id),
        parse_mode="HTML",
    )

    await callback.answer("Статус обновлён")


# ============================================================
# СТАТИСТИКА
# ============================================================

@router.callback_query(lambda c: c.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        return

    total = get_bookings_stats()

    await callback.message.edit_text(
        f"""📊 <b>Статистика CRM</b>

Всего заявок: <b>{total}</b>

🏂 Кировск
🔥 Шерегеш
🏄 Вейк
🛹 Скейт
""",
        reply_markup=admin_menu,
        parse_mode="HTML",
    )

    await callback.answer()


# ============================================================
# ЗАГЛУШКИ
# ============================================================

@router.callback_query(lambda c: c.data == "admin_tours")
async def admin_tours(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📅 Управление турами появится в CRM.",
        reply_markup=admin_menu,
    )

    await callback.answer()


@router.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "📢 Рассылку подключим в CRM.",
        reply_markup=admin_menu,
    )

    await callback.answer()


# ============================================================
# НАЗАД В АДМИН-ПАНЕЛЬ
# ============================================================

@router.callback_query(lambda c: c.data == "admin_home")
async def admin_home(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        return

    await callback.message.edit_text(
        "🛠 <b>Панель администратора WowderTour</b>",
        reply_markup=admin_menu,
        parse_mode="HTML",
    )

    await callback.answer()