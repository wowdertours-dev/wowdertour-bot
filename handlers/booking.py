from aiogram import Router
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from keyboards.booking_menu import phone_keyboard, dates_keyboard
from keyboards.main_menu import main_menu
from states.booking import BookingState
from database.db import save_booking
from data.tours import TOURS
from config import ADMIN_IDS


router = Router()


# ============================================================
# УВЕДОМЛЕНИЕ АДМИНИСТРАТОРОВ
# ============================================================

async def notify_admins(message: Message, data: dict):

    notification = (
        "🆕 <b>НОВАЯ ЗАЯВКА!</b>\n\n"
        f"👤 <b>Имя:</b> {data['full_name']}\n"
        f"📱 <b>Телефон:</b> {data['phone']}\n"
        f"🏂 <b>Тур:</b> {data['tour']}\n"
        f"📅 <b>Дата:</b> {data['tour_date']}\n"
        f"👥 <b>Количество:</b> {data['people']}\n"
        f"💬 <b>Комментарий:</b> {data['comment']}\n\n"
        f"🆔 Telegram ID: <code>{data['telegram_id']}</code>\n"
        f"👤 Username: @{data['username'] if data['username'] else 'не указан'}"
    )

    for admin_id in ADMIN_IDS:

        try:
            await message.bot.send_message(
                admin_id,
                notification,
                parse_mode="HTML",
            )

        except Exception as error:
            print(
                f"Не удалось отправить уведомление "
                f"администратору {admin_id}: {error}"
            )


# ============================================================
# НАЧАЛО ЗАПИСИ
# ============================================================

@router.callback_query(lambda c: c.data.startswith("book:"))
async def start_booking(
    callback: CallbackQuery,
    state: FSMContext
):

    tour_key = callback.data.split(":", 1)[1]
    tour = TOURS.get(tour_key)

    if not tour:
        await callback.answer(
            "Тур не найден",
            show_alert=True,
        )
        return

    await state.clear()

    await state.update_data(
        telegram_id=callback.from_user.id,
        username=callback.from_user.username,
        tour=tour["title"],
        tour_key=tour_key,
    )

    await callback.message.answer(
        f"📝 <b>Запись на тур</b>\n\n"
        f"{tour['title']}\n"
        f"💰 <b>{tour['price']:,} ₽</b>\n\n"
        f"Как тебя зовут?",
        parse_mode="HTML",
    )

    await state.set_state(
        BookingState.full_name
    )

    await callback.answer()


# ============================================================
# ИМЯ
# ============================================================

@router.message(BookingState.full_name)
async def booking_name(
    message: Message,
    state: FSMContext
):

    if not message.text:
        await message.answer(
            "Напиши своё имя текстом."
        )
        return

    await state.update_data(
        full_name=message.text.strip()
    )

    await message.answer(
        "📱 <b>Теперь отправь номер телефона.</b>",
        reply_markup=phone_keyboard,
        parse_mode="HTML",
    )

    await state.set_state(
        BookingState.phone
    )


# ============================================================
# ТЕЛЕФОН
# ============================================================

@router.message(BookingState.phone)
async def booking_phone(
    message: Message,
    state: FSMContext
):

    if message.contact:
        phone = message.contact.phone_number

    elif message.text:
        phone = message.text.strip()

    else:
        await message.answer(
            "Отправь номер телефона."
        )
        return

    await state.update_data(
        phone=phone
    )

    data = await state.get_data()

    tour = TOURS[data["tour_key"]]
    dates = tour.get("dates", [])

    # Если у тура есть даты
    if dates:

        await message.answer(
            "📅 <b>Выбери дату тура:</b>",
            reply_markup=dates_keyboard(dates),
            parse_mode="HTML",
        )

        await state.set_state(
            BookingState.tour_date
        )

    # Если даты ещё неизвестны
    else:

        await message.answer(
            "📅 <b>Точные даты пока не определены.</b>\n\n"
            "Напиши «пока неизвестно».",
            reply_markup=ReplyKeyboardRemove(),
            parse_mode="HTML",
        )

        await state.set_state(
            BookingState.tour_date
        )


# ============================================================
# ВЫБОР ДАТЫ КНОПКОЙ
# ============================================================

@router.callback_query(
    BookingState.tour_date,
    lambda c: c.data.startswith("date:")
)
async def booking_date_callback(
    callback: CallbackQuery,
    state: FSMContext
):

    date = callback.data.split(":", 1)[1]

    await state.update_data(
        tour_date=date
    )

    await callback.message.edit_text(
        f"📅 <b>Выбрана дата:</b> {date}\n\n"
        f"👥 <b>Сколько человек поедет?</b>\n\n"
        f"Напиши число.",
        parse_mode="HTML",
    )

    await state.set_state(
        BookingState.people
    )

    await callback.answer()


# ============================================================
# ДАТА ТЕКСТОМ
# ============================================================

@router.message(BookingState.tour_date)
async def booking_date(
    message: Message,
    state: FSMContext
):

    if not message.text:
        await message.answer(
            "Напиши дату текстом."
        )
        return

    await state.update_data(
        tour_date=message.text.strip()
    )

    await message.answer(
        "👥 <b>Сколько человек поедет?</b>\n\n"
        "Напиши число.",
        parse_mode="HTML",
    )

    await state.set_state(
        BookingState.people
    )


# ============================================================
# КОЛИЧЕСТВО ЛЮДЕЙ
# ============================================================

@router.message(BookingState.people)
async def booking_people(
    message: Message,
    state: FSMContext
):

    if not message.text:
        await message.answer(
            "Напиши количество человек числом."
        )
        return

    try:
        people = int(message.text.strip())

    except ValueError:
        await message.answer(
            "Напиши только число.\n\n"
            "Например: 2"
        )
        return

    if people < 1:
        await message.answer(
            "Количество человек должно быть больше 0."
        )
        return

    data = await state.get_data()

    tour = TOURS[data["tour_key"]]

    if people > tour["capacity"]:
        await message.answer(
            f"Для этого тура максимальная группа — "
            f"<b>{tour['capacity']} человек.</b>\n\n"
            f"Напиши количество от 1 до {tour['capacity']}.",
            parse_mode="HTML",
        )
        return

    await state.update_data(
        people=people
    )

    await message.answer(
        "💬 <b>Есть комментарий?</b>\n\n"
        "Например:\n"
        "• нужна аренда доски;\n"
        "• хочу отдельную комнату;\n"
        "• еду первый раз.\n\n"
        "Если комментария нет — напиши «нет».",
        parse_mode="HTML",
    )

    await state.set_state(
        BookingState.comment
    )


# ============================================================
# КОММЕНТАРИЙ + СОХРАНЕНИЕ
# ============================================================

@router.message(BookingState.comment)
async def booking_comment(
    message: Message,
    state: FSMContext
):

    if not message.text:
        await message.answer(
            "Напиши комментарий или «нет»."
        )
        return

    await state.update_data(
        comment=message.text.strip()
    )

    data = await state.get_data()

    # Сохраняем заявку
    save_booking(data)

    # Уведомляем всех администраторов
    await notify_admins(
        message,
        data,
    )

    # Очищаем состояние
    await state.clear()

    # Показываем пользователю результат
    await message.answer(
        f"🎉 <b>Заявка отправлена!</b>\n\n"
        f"🏂 <b>Тур:</b> {data['tour']}\n"
        f"📅 <b>Дата:</b> {data['tour_date']}\n"
        f"👥 <b>Количество:</b> {data['people']}\n\n"
        f"Спасибо! 🖤\n"
        f"Организатор свяжется с тобой "
        f"в ближайшее время.\n\n"
        f"Если хочешь записаться ещё на один тур — "
        f"выбери направление:",
        reply_markup=main_menu,
        parse_mode="HTML",
    )