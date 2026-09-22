import html
import logging

from aiogram import (
    F,
    Router,
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import (
    FSMContext,
)
from aiogram.types import (
    CallbackQuery,
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from app.bot.keyboards import (
    departures_keyboard,
    main_menu_keyboard,
    people_keyboard,
    phone_keyboard,
    skip_comment_keyboard,
    tour_keyboard,
)
from app.bot.states import (
    BookingState,
)
from app.core.config import settings
from app.database.session import (
    SessionLocal,
)
from app.repositories.tours import (
    can_book_departure,
    get_active_categories,
    get_bookable_departures,
    get_departure_by_id,
    get_tour_by_slug,
)
from app.services.bookings import (
    BookingService,
)


router = Router(
    name="booking"
)

logger = logging.getLogger(__name__)


CANCEL_TEXT = "Отменить оформление"


def with_cancel_button(markup=None):
    if markup is None:
        markup = InlineKeyboardMarkup(inline_keyboard=[])
    markup = markup.model_copy(deep=True)
    if isinstance(markup, InlineKeyboardMarkup):
        markup.inline_keyboard.append([
            InlineKeyboardButton(text=CANCEL_TEXT, callback_data="booking-cancel")
        ])
    elif isinstance(markup, ReplyKeyboardMarkup):
        markup.keyboard.append([KeyboardButton(text=CANCEL_TEXT)])
        markup.one_time_keyboard = False
    return markup


def format_price(
    value,
) -> str:
    return (
        f"{int(value):,}"
        .replace(",", " ")
    )


async def send_main_menu(
    message: Message,
) -> None:
    async with SessionLocal() as session:
        categories = (
            await get_active_categories(
                session
            )
        )

    await message.answer(
        (
            "👋 <b>Добро пожаловать "
            "в WowderTour!</b>\n\n"
            "Выбери направление:"
        ),
        reply_markup=(
            main_menu_keyboard(
                categories
            )
        ),
        parse_mode="HTML",
    )


@router.message(CommandStart())
async def restart_booking(
    message: Message,
    state: FSMContext,
) -> None:
    """Let the user restart even in the middle of the booking form."""
    current_state = await state.get_state()
    await state.clear()

    if current_state is not None:
        await message.answer(
            "Заявка сброшена.",
            reply_markup=ReplyKeyboardRemove(),
        )

    await send_main_menu(message)


@router.message(Command("cancel"))
async def cancel_booking(
    message: Message,
    state: FSMContext,
) -> None:
    await state.clear()
    await message.answer(
        "Заявка отменена.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await send_main_menu(message)


@router.message(F.text == CANCEL_TEXT)
async def cancel_booking_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "Оформление отменено.", reply_markup=ReplyKeyboardRemove()
    )
    await send_main_menu(message)


@router.callback_query(F.data == "booking-cancel")
async def cancel_booking_callback(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "Оформление отменено.", reply_markup=ReplyKeyboardRemove()
        )
        await send_main_menu(callback.message)


@router.callback_query(
    F.data.startswith("book:")
)
async def start_booking(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer()

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
            await callback.message.answer(
                "Этот тур сейчас недоступен."
            )
            return

        departures = (
            await get_bookable_departures(
                session,
                tour.id,
            )
        )

    if not departures:
        await callback.message.edit_text(
            (
                f"<b>{tour.title}</b>\n\n"
                "Сейчас нет открытых дат "
                "для записи."
            ),
            reply_markup=(
                tour_keyboard(
                    tour.slug,
                    tour.category.slug,
                )
            ),
            parse_mode="HTML",
        )
        return

    await state.clear()

    await state.set_state(
        BookingState.choosing_departure
    )

    await state.update_data(
        tour_slug=tour.slug,
        tour_title=tour.title,
    )

    await callback.message.edit_text(
        (
            f"<b>{tour.title}</b>\n\n"
            "Выбери дату тура 👇"
        ),
        reply_markup=(
            departures_keyboard(
                departures,
                booking=True,
                tour_slug=tour.slug,
            )
        ),
        parse_mode="HTML",
    )


@router.callback_query(
    F.data.startswith(
        "booking-date:"
    )
)
async def choose_departure(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    await callback.answer()

    try:
        departure_id = int(
            callback.data.split(
                ":",
                1,
            )[1]
        )

    except (
        TypeError,
        ValueError,
    ):
        await callback.message.answer(
            "Не удалось определить дату тура."
        )
        return

    async with SessionLocal() as session:
        departure = (
            await get_departure_by_id(
                session,
                departure_id,
            )
        )

        if departure is None:
            await callback.answer(
                "Эта дата больше недоступна.",
                show_alert=True,
            )
            return

        if not can_book_departure(
            departure
        ):
            await callback.answer(
                (
                    "На эту дату запись "
                    "уже недоступна."
                ),
                show_alert=True,
            )
            return

        await state.update_data(
            departure_id=departure.id,
            tour_title=(
                departure.tour.title
            ),
            start_date=(
                departure.start_date
                .isoformat()
            ),
            end_date=(
                departure.end_date
                .isoformat()
            ),
            price=str(
                departure.price
            ),
        )

    await state.set_state(
        BookingState.entering_name
    )

    await callback.message.edit_text(
        (
            "Как тебя зовут?\n\n"
            "Напиши имя и фамилию."
        ),
        reply_markup=with_cancel_button(),
    )


@router.message(
    BookingState.entering_name
)
async def enter_name(
    message: Message,
    state: FSMContext,
) -> None:
    full_name = (
        message.text or ""
    ).strip()

    if len(full_name) < 2:
        await message.answer(
            "Напиши имя и фамилию текстом.",
            reply_markup=with_cancel_button(),
        )
        return

    await state.update_data(
        full_name=full_name
    )

    await state.set_state(
        BookingState.entering_phone
    )

    await message.answer(
        (
            "Оставь номер телефона.\n\n"
            "Можно нажать кнопку ниже "
            "или написать номер вручную."
        ),
        reply_markup=with_cancel_button(phone_keyboard()),
    )


@router.message(
    BookingState.entering_phone,
    F.contact,
)
async def enter_phone_contact(
    message: Message,
    state: FSMContext,
) -> None:
    if (
        message.contact.user_id
        is not None
        and message.from_user
        is not None
        and message.contact.user_id
        != message.from_user.id
    ):
        await message.answer(
            (
                "Отправь, пожалуйста, "
                "свой номер телефона."
            )
        )
        return

    await save_phone_and_ask_people(
        message=message,
        state=state,
        phone=(
            message.contact.phone_number
        ),
    )


@router.message(
    BookingState.entering_phone
)
async def enter_phone_text(
    message: Message,
    state: FSMContext,
) -> None:
    phone = (
        message.text or ""
    ).strip()

    digits = "".join(
        character
        for character in phone
        if character.isdigit()
    )

    if len(digits) < 10:
        await message.answer(
            (
                "Проверь номер телефона "
                "и отправь ещё раз."
            )
        )
        return

    await save_phone_and_ask_people(
        message=message,
        state=state,
        phone=phone,
    )


async def save_phone_and_ask_people(
    *,
    message: Message,
    state: FSMContext,
    phone: str,
) -> None:
    await state.update_data(
        phone=phone
    )

    await state.set_state(
        BookingState.entering_people
    )

    await message.answer(
        "Сколько человек будет в заявке?",
        reply_markup=(
            with_cancel_button(people_keyboard())
        ),
    )


@router.message(
    BookingState.entering_people
)
async def enter_people(
    message: Message,
    state: FSMContext,
) -> None:
    try:
        people_count = int(
            (
                message.text
                or ""
            ).strip()
        )

    except ValueError:
        await message.answer(
            (
                "Напиши количество "
                "человек числом."
            )
        )
        return

    if (
        people_count < 1
        or people_count > 20
    ):
        await message.answer(
            (
                "Количество человек "
                "должно быть от 1 до 20."
            )
        )
        return

    data = await state.get_data()

    departure_id = data.get(
        "departure_id"
    )

    if departure_id is None:
        await state.clear()

        await message.answer(
            (
                "Не удалось определить "
                "дату тура. Начни заявку "
                "ещё раз."
            ),
            reply_markup=(
                ReplyKeyboardRemove()
            ),
        )

        await send_main_menu(
            message
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
            or not can_book_departure(
                departure,
                people_count,
            )
        ):
            await message.answer(
                (
                    "На выбранную дату "
                    "нельзя добавить такое "
                    "количество человек.\n\n"
                    "Укажи меньшее количество."
                )
            )
            return

    await state.update_data(
        people_count=people_count
    )

    await state.set_state(
        BookingState.entering_comment
    )

    await message.answer(
        (
            "Есть комментарий "
            "или пожелания?\n\n"
            "Если нет — нажми "
            "«Пропустить»."
        ),
        reply_markup=(
            with_cancel_button(skip_comment_keyboard())
        ),
    )


@router.message(
    BookingState.entering_comment
)
async def enter_comment(
    message: Message,
    state: FSMContext,
) -> None:
    text = (
        message.text or ""
    ).strip()

    comment = (
        None
        if text.lower()
        == "пропустить"
        else text
    )

    data = await state.get_data()

    if message.from_user is None:
        await message.answer(
            (
                "Не удалось определить "
                "пользователя."
            )
        )
        return

    try:
        async with SessionLocal() as session:
            service = BookingService(
                session
            )

            result = (
                await service.create_booking(
                    telegram_id=(
                        message.from_user.id
                    ),
                    telegram_username=(
                        message
                        .from_user
                        .username
                    ),
                    full_name=(
                        data["full_name"]
                    ),
                    phone=(
                        data["phone"]
                    ),
                    departure_id=(
                        data["departure_id"]
                    ),
                    people_count=(
                        data["people_count"]
                    ),
                    comment=comment,
                    source="telegram",
                )
            )

            # Фиксируем контактные данные именно этой заявки.
            # Даже если тот же Telegram-аккаунт позже
            # создаст другую заявку с другим именем/телефоном,
            # старая заявка останется неизменной.
            result.booking.applicant_full_name = (
                data["full_name"]
            )
            result.booking.applicant_phone = (
                data["phone"]
            )
            result.booking.applicant_telegram_username = (
                message.from_user.username
            )
            result.booking.applicant_telegram_id = (
                message.from_user.id
            )

            await session.commit()

    except ValueError as error:
        await state.clear()

        await message.answer(
            (
                "Не удалось создать "
                "заявку:\n"
                f"{error}"
            ),
            reply_markup=(
                ReplyKeyboardRemove()
            ),
        )

        await send_main_menu(
            message
        )

        return

    except Exception:
        await state.clear()

        await message.answer(
            (
                "Не удалось сохранить "
                "заявку. Попробуй ещё "
                "раз чуть позже."
            ),
            reply_markup=(
                ReplyKeyboardRemove()
            ),
        )

        await send_main_menu(
            message
        )

        raise

    departure = result.departure
    booking = result.booking

    await state.clear()

    await message.answer(
        (
            "🔥 <b>Заявка отправлена!</b>\n\n"
            f"Тур: "
            f"{departure.tour.title}\n"
            f"📅 "
            f"{departure.start_date:%d.%m.%Y}"
            " — "
            f"{departure.end_date:%d.%m.%Y}\n"
            f"👥 Человек: "
            f"{booking.people_count}\n"
            f"💰 Стоимость: "
            f"{format_price(result.total_price)} ₽\n\n"
            f"Номер заявки: "
            f"<b>#{booking.id}</b>\n\n"
            "Организатор свяжется с тобой."
        ),
        parse_mode="HTML",
        reply_markup=(
            ReplyKeyboardRemove()
        ),
    )

    await send_main_menu(
        message
    )

    username = (
        f"@{html.escape(message.from_user.username)}"
        if message.from_user.username
        else "—"
    )

    safe_name = html.escape(str(data["full_name"]))
    safe_phone = html.escape(str(data["phone"]))
    safe_comment = html.escape(comment or "—")
    safe_tour_title = html.escape(str(departure.tour.title))

    admin_text = (
        "🔥 <b>Новая заявка WowderTour</b>\n\n"
        f"Заявка: <b>#{booking.id}</b>\n"
        f"Тур: {safe_tour_title}\n"
        f"📅 "
        f"{departure.start_date:%d.%m.%Y}"
        " — "
        f"{departure.end_date:%d.%m.%Y}\n\n"
        f"👤 {safe_name}\n"
        f"📱 {safe_phone}\n"
        f"Telegram: {username}\n"
        f"Telegram ID: "
        f"<code>{message.from_user.id}</code>\n"
        f"👥 Человек: "
        f"{booking.people_count}\n"
        f"💰 Сумма: "
        f"{format_price(result.total_price)} ₽\n"
        f"🟢 Осталось мест: "
        f"{result.free_places}\n"
        f"💬 Комментарий: "
        f"{safe_comment}\n\n"
        "Статус: 🆕 Новая"
    )

    for admin_id in settings.admins:
        try:
            await message.bot.send_message(
                chat_id=admin_id,
                text=admin_text,
                parse_mode="HTML",
            )

        except Exception:
            continue