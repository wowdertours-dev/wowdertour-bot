from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from keyboards.main_menu import main_menu
router=Router()
@router.message(CommandStart())
async def start(message:Message):
 await message.answer("🖤 <b>WowderTour</b>\n\nТуры для тех, кто любит кататься, путешествовать и находить своих людей.\n\nВыбирай направление:",reply_markup=main_menu,parse_mode="HTML")
