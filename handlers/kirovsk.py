from aiogram import Router
from aiogram.types import CallbackQuery

from keyboards.main_menu import (
    ski_menu,
    kirovsk_menu,
    kirovsk_dates_menu,
)

from services.formatter import (
    kirovsk_price,
    kirovsk_dates,
)

router = Router()

@router.callback_query(lambda c: c.data == "kirovsk")
async def kirovsk(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏔 *Кировск*",
        reply_markup=kirovsk_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_ski")
async def back(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏂 *Горнолыжные туры*",
        reply_markup=ski_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "kirovsk_price")
async def price(callback: CallbackQuery):
    await callback.message.edit_text(
        kirovsk_price(),
        reply_markup=kirovsk_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "kirovsk_dates")
async def dates(callback: CallbackQuery):
    await callback.message.edit_text(
        kirovsk_dates(),
        reply_markup=kirovsk_dates_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_kirovsk")
async def back_dates(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏔 *Кировск*",
        reply_markup=kirovsk_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "kirovsk_program")
async def program(callback: CallbackQuery):
    await callback.message.edit_text(
        """
🗺️ *Программа тура*

**День 1**
✈️ Прибытие в Апатиты, трансфер до кировска, заселение, знакомство.

**День 2**
🎿 Тренировки и катание.

**День 3**
🏔️ Фрирайд с гидами.

**День 4**
🎿 Катание, вечерняя программа.

**День 5**
☕ Завтрак, выезд домой.
""",
        reply_markup=kirovsk_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "kirovsk_hotel")
async def hotel(callback: CallbackQuery):
    await callback.message.edit_text(
        """
🛏️ *Проживание*

Уютные апартаменты в хостеле Red.

✔️ Отдельные комнаты.
✔️ Кухня.
✔️ Wi-Fi.
✔️ До горы 10 минут.
""",
        reply_markup=kirovsk_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "kirovsk_media")
async def media(callback: CallbackQuery):
    await callback.message.edit_text(
        "📸 Скоро здесь будут фотографии и видео с туров.",
        reply_markup=kirovsk_menu,
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "kirovsk_booking")
async def booking(callback: CallbackQuery):
    await callback.message.edit_text(
        """
📝 *Запись на тур*

Совсем скоро здесь появится анкета записи.
""",
        reply_markup=kirovsk_menu,
        parse_mode="Markdown",
    )
    await callback.answer()