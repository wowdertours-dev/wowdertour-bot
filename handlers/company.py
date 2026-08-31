from aiogram import Router
from aiogram.types import CallbackQuery

from keyboards.main_menu import main_menu
from data.company import COMPANY

router = Router()

@router.callback_query(lambda c: c.data == "about")
async def about(callback: CallbackQuery):
    await callback.message.edit_text(
        COMPANY["about"],
        reply_markup=main_menu,
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "contacts")
async def contacts(callback: CallbackQuery):
    await callback.message.edit_text(
        COMPANY["contacts"],
        reply_markup=main_menu,
    )
    await callback.answer()