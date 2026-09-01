from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


phone_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(
                text="📱 Поделиться номером",
                request_contact=True,
            )
        ]
    ],
    resize_keyboard=True,
    one_time_keyboard=True,
)


def dates_keyboard(dates):
    buttons = []

    for date in dates:
        buttons.append([
            InlineKeyboardButton(
                text=f"📅 {date}",
                callback_data=f"date:{date}",
            )
        ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )