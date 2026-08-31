from aiogram import Router
from aiogram.types import CallbackQuery

from keyboards.main_menu import sheregesh_menu

router = Router()

@router.callback_query(lambda c: c.data == "sheregesh")
async def sheregesh(callback: CallbackQuery):
    await callback.message.edit_text(
        """
🏔 *Шерегеш*

Сейчас готовим сезон 2026/2027.

Совсем скоро появятся даты, стоимость и программа тура.
""",
        reply_markup=sheregesh_menu,
        parse_mode="Markdown",
    )
    await callback.answer()