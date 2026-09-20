from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.database.models import (
    TourCategory,
    TourDeparture,
    TourType,
)
from app.repositories.tours import (
    get_free_places,
    is_booking_closed_by_date,
    is_departure_finished,
)


def main_menu_keyboard(
    categories: list[TourCategory],
) -> InlineKeyboardMarkup:
    rows = []

    for category in categories:
        title = category.title

        if category.emoji:
            title = (
                f"{category.emoji} "
                f"{category.title}"
            )

        rows.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=(
                        f"category:{category.slug}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="ℹ️ О WowderTour",
                callback_data="about",
            ),
            InlineKeyboardButton(
                text="📞 Контакты",
                callback_data="contacts",
            ),
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def category_keyboard(
    category_slug: str,
    tours: list[TourType],
) -> InlineKeyboardMarkup:
    rows = []

    if not tours:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📸 Фотографии",
                    callback_data=(
                        f"category-photos:"
                        f"{category_slug}"
                    ),
                )
            ]
        )

    for tour in tours:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tour.title.strip(),
                    callback_data=(
                        f"tour:{tour.slug}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="← Назад",
                callback_data="main",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def tours_keyboard(
    tours: list[TourType],
) -> InlineKeyboardMarkup:
    rows = []

    for tour in tours:
        rows.append(
            [
                InlineKeyboardButton(
                    text=tour.title.strip(),
                    callback_data=(
                        f"tour:{tour.slug}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="← Назад",
                callback_data="main",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def tour_keyboard(
    slug: str,
    category_slug: str,
    *,
    has_departures: bool,
    can_book: bool,
) -> InlineKeyboardMarkup:
    rows = []

    if has_departures:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📅 Ближайшие даты",
                    callback_data=(
                        f"dates:{slug}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="📸 Фотографии",
                callback_data=(
                    f"photos:{slug}"
                ),
            )
        ]
    )

    if can_book:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📝 Оставить заявку",
                    callback_data=(
                        f"book:{slug}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="← Назад",
                callback_data=(
                    f"category:{category_slug}"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def photos_keyboard(
    slug: str,
    category_slug: str,
    *,
    has_accommodation: bool,
    has_activity: bool,
) -> InlineKeyboardMarkup:
    rows = []

    if has_accommodation:
        title = "🏠 Жильё"

        if category_slug == "wake":
            title = "🏡 Место / размещение"

        elif category_slug == "skate":
            title = "📍 Место"

        rows.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=(
                        f"media:{slug}:"
                        "accommodation"
                    ),
                )
            ]
        )

    if has_activity:
        title = "🏂 Катание и атмосфера"

        if category_slug == "wake":
            title = "🏄 Катание и атмосфера"

        elif category_slug == "skate":
            title = "🛹 Катание и атмосфера"

        rows.append(
            [
                InlineKeyboardButton(
                    text=title,
                    callback_data=(
                        f"media:{slug}:activity"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="← Назад",
                callback_data=f"tour:{slug}",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def departures_keyboard(
    departures: list[TourDeparture],
    *,
    booking: bool = False,
    tour_slug: str | None = None,
) -> InlineKeyboardMarkup:
    rows = []

    for departure in departures:
        date_text = (
            f"{departure.start_date:%d.%m}"
            "–"
            f"{departure.end_date:%d.%m.%Y}"
        )

        callback_data = (
            f"booking-date:{departure.id}"
            if booking
            else f"departure:{departure.id}"
        )

        rows.append(
            [
                InlineKeyboardButton(
                    text=date_text,
                    callback_data=callback_data,
                )
            ]
        )

    back_callback = (
        f"tour:{tour_slug}"
        if tour_slug
        else "main"
    )

    rows.append(
        [
            InlineKeyboardButton(
                text="← Назад",
                callback_data=back_callback,
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def departure_keyboard(
    departure: TourDeparture,
) -> InlineKeyboardMarkup:
    rows = []

    can_book = (
        departure.active
        and departure.booking_open
        and not is_departure_finished(
            departure
        )
        and not is_booking_closed_by_date(
            departure
        )
        and get_free_places(
            departure
        ) > 0
    )

    if can_book:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📝 Оставить заявку",
                    callback_data=(
                        f"booking-date:"
                        f"{departure.id}"
                    ),
                )
            ]
        )

    rows.append(
        [
            InlineKeyboardButton(
                text="← К датам",
                callback_data=(
                    f"dates:"
                    f"{departure.tour.slug}"
                ),
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Отправить телефон",
                    request_contact=True,
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def people_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="1"),
                KeyboardButton(text="2"),
                KeyboardButton(text="3"),
                KeyboardButton(text="4"),
            ],
            [
                KeyboardButton(text="5"),
                KeyboardButton(text="6"),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def skip_comment_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="Пропустить"
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )