from aiogram import Router
from aiogram.types import CallbackQuery

from keyboards.main_menu import wake_menu
from data.tours import WAKE

router = Router()

@router.callback_query(lambda c: c.data == "wake_tours")
async def wake(callback: CallbackQuery):
    await callback.message.edit_text(
        WAKE["description"],
        reply_markup=wake_menu,
    )
    await callback.answer()