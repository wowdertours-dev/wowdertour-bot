from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
main_menu=InlineKeyboardMarkup(inline_keyboard=[
 [InlineKeyboardButton(text="🏂 Сноуборд-туры",callback_data="snow")],
 [InlineKeyboardButton(text="🏄 Вейк",callback_data="tour:wake"),InlineKeyboardButton(text="🛹 Скейт",callback_data="tour:skate")],
 [InlineKeyboardButton(text="👤 О WowderTour",callback_data="about"),InlineKeyboardButton(text="📞 Контакты",callback_data="contacts")],
])
