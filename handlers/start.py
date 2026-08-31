from aiogram import Router
from aiogram.filters import CommandStart

from keyboards.main_menu import main_menu

router = Router()

@router.message(CommandStart())
async def start(message):
    await message.answer(
        "👋 *Добро пожаловать в Wowder Tour!*\n\nВыбери направление:",
        reply_markup=main_menu,
        parse_mode="Markdown",
    )