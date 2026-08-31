from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ---------- Главное меню ----------

main_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🏂 Горнолыжные туры", callback_data="ski_tours")],
        [InlineKeyboardButton(text="🌊 Вейк-туры", callback_data="wake_tours")],
        [InlineKeyboardButton(text="🛹 Скейт-интенсивы", callback_data="skate_tours")],
        [InlineKeyboardButton(text="ℹ️ О WowderTour", callback_data="about")],
        [InlineKeyboardButton(text="📞 Контакты", callback_data="contacts")],
    ]
)

# ---------- Горнолыжные ----------

ski_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="🏔 Кировск", callback_data="kirovsk")],
        [InlineKeyboardButton(text="🏔 Шерегеш", callback_data="sheregesh")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ]
)

# ---------- Кировск ----------

kirovsk_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ближайшие туры", callback_data="kirovsk_dates")],
        [InlineKeyboardButton(text="💰 Стоимость", callback_data="kirovsk_price")],
        [InlineKeyboardButton(text="🗺️ Программа тура", callback_data="kirovsk_program")],
        [InlineKeyboardButton(text="🛏️ Проживание", callback_data="kirovsk_hotel")],
        [InlineKeyboardButton(text="📸 Фото и видео", callback_data="kirovsk_media")],
        [InlineKeyboardButton(text="📝 Записаться", callback_data="kirovsk_booking")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_ski")],
    ]
)

kirovsk_dates_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📝 Записаться на тур", callback_data="kirovsk_booking")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_kirovsk")],
    ]
)

# ---------- Шерегеш ----------

sheregesh_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ближайшие туры", callback_data="sheregesh_dates")],
        [InlineKeyboardButton(text="💰 Стоимость", callback_data="sheregesh_price")],
        [InlineKeyboardButton(text="🗺️ Программа тура", callback_data="sheregesh_program")],
        [InlineKeyboardButton(text="🛏️ Проживание", callback_data="sheregesh_hotel")],
        [InlineKeyboardButton(text="📸 Фото и видео", callback_data="sheregesh_media")],
        [InlineKeyboardButton(text="📝 Записаться", callback_data="sheregesh_booking")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_ski")],
    ]
)

# ---------- Вейк ----------

wake_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ближайшие туры", callback_data="wake_dates")],
        [InlineKeyboardButton(text="💰 Стоимость", callback_data="wake_price")],
        [InlineKeyboardButton(text="🌊 Программа тура", callback_data="wake_program")],
        [InlineKeyboardButton(text="🛏️ Проживание", callback_data="wake_hotel")],
        [InlineKeyboardButton(text="📸 Фото и видео", callback_data="wake_media")],
        [InlineKeyboardButton(text="📝 Записаться", callback_data="wake_booking")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ]
)

# ---------- Скейт ----------

skate_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="📅 Ближайшие интенсивы", callback_data="skate_dates")],
        [InlineKeyboardButton(text="💰 Стоимость", callback_data="skate_price")],
        [InlineKeyboardButton(text="🛹 Что входит", callback_data="skate_program")],
        [InlineKeyboardButton(text="📍 Локации", callback_data="skate_locations")],
        [InlineKeyboardButton(text="📸 Фото и видео", callback_data="skate_media")],
        [InlineKeyboardButton(text="📝 Записаться", callback_data="skate_booking")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_main")],
    ]
)