from aiogram import Router
from aiogram.types import CallbackQuery

from keyboards.main_menu import ski_menu, main_menu

router = Router()

@router.callback_query(lambda c: c.data == "ski_tours")
async def ski(callback: CallbackQuery):
    await callback.message.edit_text(
        "🏂 *Горнолыжные туры*",
        reply_markup=ski_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "back_main")
async def back(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 *Добро пожаловать в Wowder Tour!*",
        reply_markup=main_menu,
        parse_mode="Markdown",
    )
    await callback.answer()