from aiogram import Router
from aiogram.types import CallbackQuery

from keyboards.main_menu import skate_menu
from data.tours import SKATE

router = Router()

@router.callback_query(lambda c: c.data == "skate_tours")
async def skate(callback: CallbackQuery):
    await callback.message.edit_text(
        SKATE["description"],
        reply_markup=skate_menu,
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "skate_dates")
async def skate_dates(callback: CallbackQuery):

    dates = "\n".join(f"• {d}" for d in SKATE["dates"])

    await callback.message.edit_text(
        f"""
🛹 *Ближайшие интенсивы*

{dates}
""",
        reply_markup=skate_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data == "skate_price")
async def skate_price(callback: CallbackQuery):
    await callback.message.edit_text(
        f"""
🛹 *Стоимость интенсива*

💰 {SKATE["price"]} ₽

Однодневный интенсив включает тренировку и сопровождение тренера.
""",
        reply_markup=skate_menu,
        parse_mode="Markdown",
    )
    await callback.answer()

@router.callback_query(lambda c: c.data.startswith("skate_"))
async def skate_stub(callback: CallbackQuery):
    await callback.message.edit_text(
        "🛹 Этот раздел скоро появится.",
        reply_markup=skate_menu,
    )
    await callback.answer()