import base64
import binascii

from aiogram import (
    F,
    Router,
)
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import CommandStart
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    Message,
)

from app.bot.keyboards import (
    category_keyboard,
    departure_keyboard,
    departures_keyboard,
    main_menu_keyboard,
    tour_keyboard,
)
from app.database.session import (
    SessionLocal,
)
from app.repositories.tours import (
    get_about_media,
    get_active_categories,
    get_active_departures,
    get_active_tours_by_category,
    get_bookable_departures,
    get_category_by_slug,
    get_departure_by_id,
    get_free_places,
    get_tour_by_slug,
    is_booking_closed_by_date,
    is_departure_finished,
)


router = Router()


def format_money(
    value,
) -> str:
    return (
        f"{int(value):,}"
        .replace(",", " ")
    )


def direction_keyboard(
    *,
    tour,
    has_departures: bool,
    can_book: bool,
    has_housing: bool,
    has_includes: bool,
    has_program: bool,
    has_atmosphere: bool,
) -> InlineKeyboardMarkup:
    rows = []

    if has_departures:
        rows.append([
            InlineKeyboardButton(
                text="📅 Ближайшие даты",
                callback_data=f"dates:{tour.slug}",
            )
        ])

    if has_housing:
        rows.append([
            InlineKeyboardButton(
                text="🏠 Жильё",
                callback_data=f"housing:{tour.slug}",
            )
        ])

    if has_includes:
        rows.append([
            InlineKeyboardButton(
                text="🎁 Что входит",
                callback_data=f"includes:{tour.slug}",
            )
        ])

    if has_program:
        rows.append([
            InlineKeyboardButton(
                text="🗓 Программа тура",
                callback_data=f"program:{tour.slug}",
            )
        ])

    if has_atmosphere:
        rows.append([
            InlineKeyboardButton(
                text="📸 Атмосфера",
                callback_data=f"photos:{tour.slug}",
            )
        ])

    if can_book:
        rows.append([
            InlineKeyboardButton(
                text="✅ Оставить заявку",
                callback_data=f"book:{tour.slug}",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="← Назад",
            callback_data=f"category:{tour.category.slug}",
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def housing_keyboard(
    *,
    tour,
    has_photos: bool,
) -> InlineKeyboardMarkup:
    rows = []

    if has_photos:
        rows.append([
            InlineKeyboardButton(
                text="📸 Фото жилья",
                callback_data=(
                    f"media:{tour.slug}:accommodation"
                ),
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text="← К направлению",
            callback_data=f"tour:{tour.slug}",
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


def info_back_keyboard(
    tour,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="← К направлению",
                    callback_data=f"tour:{tour.slug}",
                )
            ]
        ]
    )


def get_media_source(
    media,
):
    if media.telegram_file_id:
        return media.telegram_file_id

    if not media.url:
        return None

    if (
        media.url.startswith("data:image/")
        and ";base64," in media.url
    ):
        try:
            header, encoded = media.url.split(
                ",",
                1,
            )
            image_format = (
                header
                .split("/", 1)[1]
                .split(";", 1)[0]
                .lower()
            )
            image_bytes = base64.b64decode(
                encoded,
                validate=True,
            )
        except (
            ValueError,
            binascii.Error,
            IndexError,
        ):
            return None

        extension = {
            "jpeg": "jpg",
            "jpg": "jpg",
            "png": "png",
            "webp": "webp",
        }.get(
            image_format,
            "jpg",
        )

        return BufferedInputFile(
            image_bytes,
            filename=(
                f"wowdertour_{media.id}."
                f"{extension}"
            ),
        )

    return media.url


async def remove_menu_message(
    callback: CallbackQuery,
):
    try:
        await callback.message.delete()
    except TelegramBadRequest:
        pass


async def send_photos(
    message,
    media_items,
    caption: str,
):
    prepared_media = []

    for item in media_items:
        source = get_media_source(item)

        if source is not None:
            prepared_media.append(
                (item, source)
            )

    prepared_media.sort(
        key=lambda pair: (
            pair[0].sort_order,
            pair[0].id,
        )
    )

    if not prepared_media:
        return False

    for start in range(
        0,
        len(prepared_media),
        10,
    ):
        chunk = prepared_media[
            start:start + 10
        ]

        if len(chunk) == 1:
            _, source = chunk[0]

            await message.answer_photo(
                photo=source,
                caption=(
                    caption
                    if start == 0
                    else None
                ),
                protect_content=True,
            )

            continue

        album = []

        for index, (_, source) in enumerate(
            chunk
        ):
            photo_caption = None

            if (
                start == 0
                and index == 0
            ):
                photo_caption = caption

            album.append(
                InputMediaPhoto(
                    media=source,
                    caption=photo_caption,
                )
            )

        await message.answer_media_group(
            media=album,
            protect_content=True,
        )

    return True


async def show_main_menu(
    *,
    message,
    edit: bool = False,
):
    async with SessionLocal() as session:
        categories = (
            await get_active_categories(
                session
            )
        )

    text = (
        "👋 <b>Добро пожаловать "
        "в WowderTour!</b>\n\n"
        "Выбери формат тура:"
    )

    keyboard = main_menu_keyboard(
        categories
    )

    if edit:
        await message.edit_text(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )
    else:
        await message.answer(
            text,
            reply_markup=keyboard,
            parse_mode="HTML",
        )


@router.message(
    CommandStart()
)
async def start_handler(
    message: Message,
):
    await show_main_menu(
        message=message,
    )


@router.callback_query(
    F.data == "main"
)
async def main_callback(
    callback: CallbackQuery,
):
    await show_main_menu(
        message=callback.message,
        edit=True,
    )

    await callback.answer()


@router.callback_query(
    F.data.startswith("category:")
)
async def category_callback(
    callback: CallbackQuery,
):
    slug = callback.data.split(
        ":",
        1,
    )[1]

    async with SessionLocal() as session:
        category = (
            await get_category_by_slug(
                session,
                slug,
            )
        )

        if category is None:
            await callback.answer(
                "Категория недоступна",
                show_alert=True,
            )
            return

        tours = (
            await get_active_tours_by_category(
                session,
                category.id,
            )
        )

    title = category.title

    if category.emoji:
        title = (
            f"{category.emoji} "
            f"{category.title}"
        )

    if tours:
        text = (
            f"<b>{title}</b>\n\n"
            "Куда поедем?"
        )

    else:
        text = (
            f"<b>{title}</b>\n\n"
            "Новые поездки скоро появятся.\n\n"
            "А пока можно посмотреть "
            "фотографии наших прошлых "
            "выездов и атмосферу."
        )

    await callback.message.edit_text(
        text,
        reply_markup=(
            category_keyboard(
                category.slug,
                tours,
            )
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data.startswith(
        "category-photos:"
    )
)
async def category_photos_callback(
    callback: CallbackQuery,
):
    slug = callback.data.split(
        ":",
        1,
    )[1]

    async with SessionLocal() as session:
        category = (
            await get_category_by_slug(
                session,
                slug,
            )
        )

    if category is None:
        await callback.answer(
            "Категория недоступна",
            show_alert=True,
        )
        return

    media_items = [
        item
        for item in category.media
        if (
            item.active
            and item.media_type == "photo"
            and get_media_source(item)
        )
    ]

    title = category.title

    if category.emoji:
        title = (
            f"{category.emoji} "
            f"{category.title}"
        )

    if not media_items:
        await callback.answer(
            "Фото скоро добавим 📸",
            show_alert=True,
        )
        return

    await callback.answer()
    await remove_menu_message(callback)

    sent = await send_photos(
        callback.message,
        media_items,
        f"📸 {title}",
    )

    if not sent:
        await callback.message.answer(
            "Не удалось отправить фотографии.",
        )
        return

    await callback.message.answer(
        "Продолжим?",
        reply_markup=(
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="← К категории",
                            callback_data=(
                                f"category:{slug}"
                            ),
                        )
                    ]
                ]
            )
        ),
    )


@router.callback_query(
    F.data.startswith("tour:")
)
async def tour_callback(
    callback: CallbackQuery,
):
    slug = callback.data.split(
        ":",
        1,
    )[1]

    async with SessionLocal() as session:
        tour = await get_tour_by_slug(
            session,
            slug,
        )

        if tour is None:
            await callback.answer(
                "Направление недоступно",
                show_alert=True,
            )
            return

        departures = (
            await get_active_departures(
                session,
                tour.id,
            )
        )

        bookable_departures = (
            await get_bookable_departures(
                session,
                tour.id,
            )
        )

    text_parts = [
        f"🏔️ <b>{tour.title}</b>",
    ]

    if tour.description:
        text_parts.append(
            tour.description
        )

    if departures:
        min_price = min(
            departure.price
            for departure in departures
        )

        text_parts.append(
            (
                f"💰 от "
                f"{format_money(min_price)} ₽\n"
                f"📅 Ближайших выездов: "
                f"{len(departures)}"
            )
        )

    else:
        text_parts.append(
            "📅 Новых поездок пока нет."
        )

    has_housing_photos = any(
        media.active
        and media.section == "accommodation"
        and get_media_source(media)
        for media in tour.media
    )

    has_atmosphere = any(
        media.active
        and media.section == "activity"
        and get_media_source(media)
        for media in tour.media
    )

    has_housing = bool(
        tour.accommodation_description
        or has_housing_photos
    )

    await callback.message.edit_text(
        "\n\n".join(text_parts),
        reply_markup=(
            direction_keyboard(
                tour=tour,
                has_departures=bool(
                    departures
                ),
                can_book=bool(
                    bookable_departures
                ),
                has_housing=has_housing,
                has_includes=bool(
                    tour.includes
                ),
                has_program=bool(
                    tour.program
                ),
                has_atmosphere=has_atmosphere,
            )
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data.startswith("includes:")
)
async def includes_callback(
    callback: CallbackQuery,
):
    slug = callback.data.split(
        ":",
        1,
    )[1]

    async with SessionLocal() as session:
        tour = await get_tour_by_slug(
            session,
            slug,
        )

    if tour is None:
        await callback.answer(
            "Направление недоступно",
            show_alert=True,
        )
        return

    if not tour.includes:
        await callback.answer(
            "Информация скоро появится",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        (
            f"✅ <b>{tour.title} — "
            "что входит в стоимость</b>\n\n"
            f"{tour.includes}"
        ),
        reply_markup=info_back_keyboard(
            tour
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data.startswith("program:")
)
async def program_callback(
    callback: CallbackQuery,
):
    slug = callback.data.split(
        ":",
        1,
    )[1]

    async with SessionLocal() as session:
        tour = await get_tour_by_slug(
            session,
            slug,
        )

    if tour is None:
        await callback.answer(
            "Направление недоступно",
            show_alert=True,
        )
        return

    if not tour.program:
        await callback.answer(
            "Программа скоро появится",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        (
            f"🗓 <b>{tour.title} — "
            "программа тура</b>\n\n"
            f"{tour.program}"
        ),
        reply_markup=info_back_keyboard(
            tour
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data.startswith("housing:")
)
async def housing_callback(
    callback: CallbackQuery,
):
    slug = callback.data.split(
        ":",
        1,
    )[1]

    async with SessionLocal() as session:
        tour = await get_tour_by_slug(
            session,
            slug,
        )

    if tour is None:
        await callback.answer(
            "Направление недоступно",
            show_alert=True,
        )
        return

    housing_photos = [
        media
        for media in tour.media
        if (
            media.active
            and media.section
            == "accommodation"
            and get_media_source(media)
        )
    ]

    description = (
        tour.accommodation_description
        or "Описание жилья скоро добавим."
    )

    await callback.message.edit_text(
        (
            f"🏠 <b>{tour.title} — жильё</b>\n\n"
            f"{description}"
        ),
        reply_markup=(
            housing_keyboard(
                tour=tour,
                has_photos=bool(
                    housing_photos
                ),
            )
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data.startswith("photos:")
)
async def photos_callback(
    callback: CallbackQuery,
):
    slug = callback.data.split(
        ":",
        1,
    )[1]

    async with SessionLocal() as session:
        tour = await get_tour_by_slug(
            session,
            slug,
        )

    if tour is None:
        await callback.answer(
            "Направление недоступно",
            show_alert=True,
        )
        return

    atmosphere = [
        media
        for media in tour.media
        if (
            media.active
            and media.section == "activity"
            and get_media_source(media)
        )
    ]

    if not atmosphere:
        await callback.answer(
            "Фото атмосферы скоро добавим 📸",
            show_alert=True,
        )
        return

    await callback.answer()
    await remove_menu_message(callback)

    sent = await send_photos(
        callback.message,
        atmosphere,
        f"📸 {tour.title} — атмосфера",
    )

    if not sent:
        await callback.message.answer(
            "Не удалось отправить фотографии.",
        )
        return

    await callback.message.answer(
        "Продолжим?",
        reply_markup=(
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="← К направлению",
                            callback_data=(
                                f"tour:{tour.slug}"
                            ),
                        )
                    ]
                ]
            )
        ),
    )


@router.callback_query(
    F.data.startswith("media:")
)
async def media_callback(
    callback: CallbackQuery,
):
    parts = callback.data.split(
        ":",
        2,
    )

    if len(parts) != 3:
        await callback.answer(
            "Ошибка галереи",
            show_alert=True,
        )
        return

    slug = parts[1]
    section = parts[2]

    async with SessionLocal() as session:
        tour = await get_tour_by_slug(
            session,
            slug,
        )

    if tour is None:
        await callback.answer(
            "Направление недоступно",
            show_alert=True,
        )
        return

    media_items = [
        media
        for media in tour.media
        if (
            media.active
            and media.section == section
            and get_media_source(media)
        )
    ]

    if section == "accommodation":
        caption = (
            f"🏠 {tour.title} — жильё"
        )
    else:
        caption = (
            f"📸 {tour.title} — атмосфера"
        )

    if not media_items:
        await callback.answer(
            "Фото пока не добавлены",
            show_alert=True,
        )
        return

    await callback.answer()
    await remove_menu_message(callback)

    sent = await send_photos(
        callback.message,
        media_items,
        caption,
    )

    if not sent:
        await callback.message.answer(
            "Не удалось отправить фотографии.",
        )
        return

    back_callback = (
        f"housing:{tour.slug}"
        if section == "accommodation"
        else f"tour:{tour.slug}"
    )

    back_text = (
        "← К жилью"
        if section == "accommodation"
        else "← К направлению"
    )

    await callback.message.answer(
        "Продолжим?",
        reply_markup=(
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=back_text,
                            callback_data=back_callback,
                        )
                    ]
                ]
            )
        ),
    )


@router.callback_query(
    F.data.startswith("dates:")
)
async def dates_callback(
    callback: CallbackQuery,
):
    slug = callback.data.split(
        ":",
        1,
    )[1]

    async with SessionLocal() as session:
        tour = await get_tour_by_slug(
            session,
            slug,
        )

        if tour is None:
            await callback.answer(
                "Направление недоступно",
                show_alert=True,
            )
            return

        departures = (
            await get_active_departures(
                session,
                tour.id,
            )
        )

    if not departures:
        await callback.answer(
            "Новых поездок пока нет.",
            show_alert=True,
        )
        return

    await callback.message.edit_text(
        (
            f"📅 <b>{tour.title}</b>\n\n"
            "Выбери дату:"
        ),
        reply_markup=(
            departures_keyboard(
                departures,
                tour_slug=tour.slug,
            )
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data.startswith("departure:")
)
async def departure_callback(
    callback: CallbackQuery,
):
    try:
        departure_id = int(
            callback.data.split(
                ":",
                1,
            )[1]
        )

    except ValueError:
        await callback.answer(
            "Некорректная дата",
            show_alert=True,
        )
        return

    async with SessionLocal() as session:
        departure = (
            await get_departure_by_id(
                session,
                departure_id,
            )
        )

        if (
            departure is None
            or not departure.active
            or departure.archived
            or is_departure_finished(
                departure
            )
        ):
            await callback.answer(
                "Этот выезд больше недоступен",
                show_alert=True,
            )
            return

        free_places = (
            get_free_places(
                departure
            )
        )

    if is_booking_closed_by_date(
        departure
    ):
        booking_text = (
            "⛔ Запись закрыта"
        )

    elif not departure.booking_open:
        booking_text = (
            "⛔ Продажи закрыты"
        )

    elif free_places <= 0:
        booking_text = (
            "⛔ Мест больше нет"
        )

    else:
        booking_text = (
            "✅ Заявки принимаются"
        )

    text = (
        f"🏔️ <b>"
        f"{departure.tour.title}"
        f"</b>\n\n"
        f"📅 "
        f"{departure.start_date:%d.%m.%Y}"
        " — "
        f"{departure.end_date:%d.%m.%Y}\n\n"
        f"💰 "
        f"{format_money(departure.price)} ₽\n\n"
        f"{booking_text}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=(
            departure_keyboard(
                departure
            )
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data == "about"
)
async def about_callback(
    callback: CallbackQuery,
):
    await callback.message.edit_text(
        (
            "ℹ️ <b>О WowderTour</b>\n\n"
            "<b>WOWDERTOUR — активные поездки "
            "для тех, кто любит спорт, новые "
            "эмоции и хорошую компанию.</b>\n\n"
            "Мы организуем сноуборд-туры, "
            "вейк-туры и скейт-интенсивы — "
            "с продуманной программой, "
            "сильными инструкторами и "
            "опытными гидами.\n\n"
            "Можно ехать одному, попробовать "
            "новое, прокачать навыки и провести "
            "время среди людей с похожими "
            "интересами.\n\n"
            "🏂 Сноуборд\n"
            "🏄 Вейк\n"
            "🛹 Скейт\n\n"
            "<b>Что тебя ждёт:</b>\n"
            "• обучение и помощь на катании\n"
            "• опытные гиды и инструкторы\n"
            "• небольшие группы\n"
            "• организаторы рядом\n"
            "• новые знакомства\n"
            "• совместные активности "
            "вне катания\n\n"
            "🎉 После катания — ужины, игры, "
            "кино, баня, прогулки и другая "
            "движуха."
        ),
        reply_markup=(
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📸 Наша атмосфера",
                            callback_data=(
                                "about-photos"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="📞 Контакты",
                            callback_data="contacts",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="← Назад",
                            callback_data="main",
                        )
                    ],
                ]
            )
        ),
        parse_mode="HTML",
    )

    await callback.answer()


@router.callback_query(
    F.data == "about-photos"
)
async def about_photos_callback(
    callback: CallbackQuery,
):
    async with SessionLocal() as session:
        media_items = (
            await get_about_media(
                session
            )
        )

    if not media_items:
        await callback.answer(
            "Фото скоро добавим 📸",
            show_alert=True,
        )
        return

    await callback.answer()
    await remove_menu_message(callback)

    sent = await send_photos(
        callback.message,
        media_items,
        "📸 Атмосфера WowderTour",
    )

    if not sent:
        await callback.message.answer(
            "Не удалось отправить фотографии.",
        )
        return

    await callback.message.answer(
        "WowderTour — это не только катание 🙌",
        reply_markup=(
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="← О WowderTour",
                            callback_data="about",
                        )
                    ]
                ]
            )
        ),
    )


@router.callback_query(
    F.data == "contacts"
)
async def contacts_callback(
    callback: CallbackQuery,
):
    await callback.message.edit_text(
        (
            "📞 <b>Контакты WowderTour</b>\n\n"
            "Выбери удобный способ связи:"
        ),
        reply_markup=(
            InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="📸 Instagram",
                            url=(
                                "https://www.instagram.com/"
                                "wowdertour?igsi=bjgyanRqdWVtdzMx"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=(
                                "👤 Telegram организатора"
                            ),
                            url=(
                                "https://t.me/"
                                "alexandra_xa"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text=(
                                "💬 Telegram WowderTour"
                            ),
                            url=(
                                "https://t.me/"
                                "+fR4EZEP8astiZjhi"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="💙 ВКонтакте",
                            url=(
                                "https://vk.ru/"
                                "wowdertour"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="← Назад",
                            callback_data="main",
                        )
                    ],
                ]
            )
        ),
        parse_mode="HTML",
    )

    await callback.answer()
