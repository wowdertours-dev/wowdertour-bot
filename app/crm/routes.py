from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Form, Query, Request
from fastapi.responses import (
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import (
    AccommodationRate,
    Booking,
    Customer,
    Participant,
    Payment,
    PaymentRefund,
    Room,
    TourDeparture,
)
from app.core.booking_number import booking_public_number
from app.database.session import SessionLocal
from app.crm.seasons import available_seasons, current_season_label, departure_season, normalize_season
from app.crm.departure_export import build_departure_xlsx


router = APIRouter()


BOOKING_STATUSES = [
    "Новая",
    "Связались",
    "Предоплата",
    "Оплачено",
    "Не актуальна",
    "Отмена",
]

CLOSED_BOOKING_STATUSES = {
    "Не актуальна",
    "Отмена",
}

SUCCESS_PAYMENT_STATUSES = {
    "paid",
    "succeeded",
}

SUCCESS_REFUND_STATUSES = {
    "succeeded",
}


def format_money(value) -> str:
    if value is None:
        return "0"

    return f"{int(value):,}".replace(
        ",",
        " ",
    )


def natural_text_key(value) -> tuple:
    """
    Простая естественная сортировка:
    2, 3, 10 вместо 10, 2, 3.
    """
    text = str(value or "").strip()

    if text.isdigit():
        return (0, int(text))

    return (1, text.lower())


def payment_refunded_total(
    payment: Payment,
) -> Decimal:
    return sum(
        (
            Decimal(refund.amount)
            for refund in payment.refunds
            if (
                refund.status
                in SUCCESS_REFUND_STATUSES
                and Decimal(refund.amount) > 0
            )
        ),
        Decimal("0"),
    )


def booking_gross_paid_total(
    booking: Booking,
) -> Decimal:
    return sum(
        (
            Decimal(payment.amount)
            for payment in booking.payments
            if (
                payment.status
                in SUCCESS_PAYMENT_STATUSES
                and Decimal(payment.amount) > 0
            )
        ),
        Decimal("0"),
    )


def booking_refunded_total(
    booking: Booking,
) -> Decimal:
    return sum(
        (
            payment_refunded_total(payment)
            for payment in booking.payments
            if payment.status in SUCCESS_PAYMENT_STATUSES
        ),
        Decimal("0"),
    )


def booking_paid_total(
    booking: Booking,
) -> Decimal:
    """Чистая оплата: поступления минус фактические возвраты."""
    return max(
        booking_gross_paid_total(booking)
        - booking_refunded_total(booking),
        Decimal("0"),
    )


def booking_reserves_places(
    booking: Booking,
) -> bool:
    if booking.status in CLOSED_BOOKING_STATUSES:
        return False

    return booking_paid_total(booking) > 0


def departure_reserved_places(
    departure: TourDeparture,
) -> int:
    return sum(
        booking.people_count
        for booking in departure.bookings
        if booking_reserves_places(booking)
    )


async def sync_booking_payment_status(
    session,
    booking: Booking,
):
    # Отменённую заявку не меняем автоматически.
    if booking.status == "Отмена":
        return

    await session.flush()

    result = await session.execute(
        select(Booking)
        .options(
            selectinload(Booking.payments)
            .selectinload(Payment.refunds)
        )
        .where(Booking.id == booking.id)
        .execution_options(populate_existing=True)
    )
    loaded_booking = result.scalars().unique().one()
    paid_total = booking_paid_total(loaded_booking)

    total_price = Decimal(
        booking.agreed_price or 0
    )

    if (
        total_price > 0
        and paid_total >= total_price
    ):
        booking.status = "Оплачено"

    elif paid_total > 0:
        booking.status = "Предоплата"

    elif booking.status in {
        "Предоплата",
        "Оплачено",
    }:
        booking.status = "Связались"


async def get_departure(
    session,
    departure_id: int,
):
    result = await session.execute(
        select(TourDeparture)
        .options(
            selectinload(
                TourDeparture.tour
            ),
            selectinload(
                TourDeparture.accommodation_rates
            ),
            selectinload(
                TourDeparture.rooms
            ).selectinload(
                Room.participants
            ),
            selectinload(
                TourDeparture.bookings
            ).selectinload(
                Booking.customer
            ),
            selectinload(
                TourDeparture.bookings
            ).selectinload(
                Booking.payments
            ).selectinload(
                Payment.refunds
            ),
            selectinload(
                TourDeparture.bookings
            ).selectinload(
                Booking.participants
            ).selectinload(
                Participant.room
            ),
            selectinload(
                TourDeparture.bookings
            ).selectinload(
                Booking.participants
            ).selectinload(
                Participant.accommodation_rate
            ),
        )
        .where(
            TourDeparture.id
            == departure_id
        )
    )

    return result.scalar_one_or_none()


async def ensure_participants(
    session,
    departure: TourDeparture,
):
    changed = False

    for booking in departure.bookings:
        existing_count = len(
            booking.participants
        )

        missing_count = (
            booking.people_count
            - existing_count
        )

        if missing_count <= 0:
            continue

        for index in range(
            existing_count,
            booking.people_count,
        ):
            if index == 0:
                participant_name = (
                    booking.customer.full_name
                )
            else:
                participant_name = (
                    f"Участник {index + 1}"
                )

            participant = Participant(
                booking_id=booking.id,
                full_name=participant_name,
                accommodation_type=None,
                accommodation_price=None,
                occupied_beds=1,
                ticket_status="Не куплен",
                comment=None,
            )

            session.add(participant)
            changed = True

    if changed:
        await session.commit()


def build_room_cards(
    departure: TourDeparture,
):
    cards = []

    rooms = sorted(
        departure.rooms,
        key=lambda room:
            natural_text_key(room.number),
    )

    for room in rooms:
        occupied_beds = sum(
            participant.occupied_beds
            for participant
            in room.participants
        )

        capacity = (
            room.capacity
            or 0
        )

        free_beds = max(
            capacity - occupied_beds,
            0,
        )

        single_occupancy = any(
            capacity > 0
            and participant.occupied_beds
            >= capacity
            for participant
            in room.participants
        )

        cards.append(
            {
                "room": room,
                "occupied_beds":
                    occupied_beds,
                "free_beds":
                    free_beds,
                "is_full":
                    capacity > 0
                    and occupied_beds
                    >= capacity,
                "single_occupancy":
                    single_occupancy,
            }
        )

    return cards


@router.get(
    "/",
    response_class=HTMLResponse,
)
async def dashboard(
    request: Request,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourDeparture)
            .options(
                selectinload(
                    TourDeparture.tour
                ),
                selectinload(
                    TourDeparture.bookings
                ).selectinload(
                    Booking.customer
                ),
                selectinload(
                    TourDeparture.bookings
                ).selectinload(
                    Booking.payments
                ).selectinload(
                    Payment.refunds
                ),
            )
            .where(
                TourDeparture.active.is_(
                    True
                )
            )
            .order_by(
                TourDeparture.start_date
            )
        )

        departures = list(
            result.scalars()
            .unique()
            .all()
        )

        cards = []

        for departure in departures:
            active_bookings = [
                booking
                for booking
                in departure.bookings
                if booking.status
                not in CLOSED_BOOKING_STATUSES
            ]

            people_count = (
                departure_reserved_places(
                    departure
                )
            )

            revenue = sum(
                (
                    booking.agreed_price
                    for booking
                    in active_bookings
                ),
                Decimal("0"),
            )

            paid = sum(
                (
                    booking_paid_total(booking)
                    for booking in active_bookings
                ),
                Decimal("0"),
            )

            remaining = max(
                revenue - paid,
                Decimal("0"),
            )

            cards.append(
                {
                    "departure":
                        departure,
                    "people_count":
                        people_count,
                    "free_places":
                        max(
                            departure.capacity
                            - people_count,
                            0,
                        ),
                    "revenue":
                        revenue,
                    "paid":
                        paid,
                    "remaining":
                        remaining,
                }
            )

    return (
        request.app.state.templates
        .TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "cards": cards,
                "format_money":
                    format_money,
                "payment_refunded_total":
                    payment_refunded_total,
                "booking_public_number":
                    booking_public_number,
            },
        )
    )



@router.get(
    "/bookings",
    response_class=HTMLResponse,
)
async def bookings_page(
    request: Request,
    q: str = Query(""),
    status: str = Query(""),
    departure_id: str = Query(""),
    sort: str = Query("newest"),
):
    """
    Общая страница заявок.

    Для небольшого проекта фильтрация и сортировка
    делаются в Python после одного компактного запроса:
    это проще и прозрачнее сложной SQL-воронки.
    """
    allowed_sorts = {
        "newest",
        "oldest",
        "name",
        "amount_desc",
        "amount_asc",
    }

    if sort not in allowed_sorts:
        sort = "newest"

    q = q.strip()
    status = status.strip()

    selected_departure_id = None

    if departure_id.strip():
        try:
            selected_departure_id = int(
                departure_id
            )
        except ValueError:
            selected_departure_id = None

    async with SessionLocal() as session:
        result = await session.execute(
            select(Booking)
            .options(
                selectinload(
                    Booking.customer
                ),
                selectinload(
                    Booking.departure
                ).selectinload(
                    TourDeparture.tour
                ),
                selectinload(
                    Booking.payments
                ).selectinload(
                    Payment.refunds
                ),
            )
        )

        bookings = list(
            result.scalars()
            .unique()
            .all()
        )

        departures_result = await session.execute(
            select(TourDeparture)
            .options(
                selectinload(
                    TourDeparture.tour
                )
            )
            .order_by(
                TourDeparture.start_date.desc()
            )
        )

        departures = list(
            departures_result.scalars()
            .unique()
            .all()
        )

    if status:
        bookings = [
            booking
            for booking in bookings
            if booking.status == status
        ]

    if selected_departure_id is not None:
        bookings = [
            booking
            for booking in bookings
            if booking.departure_id
            == selected_departure_id
        ]

    if q:
        needle = q.lower()

        bookings = [
            booking
            for booking in bookings
            if (
                needle
                in (
                    booking.applicant_full_name
                    or booking.customer.full_name
                    or ""
                ).lower()
                or needle
                in (
                    booking.applicant_phone
                    or booking.customer.phone
                    or ""
                ).lower()
                or needle
                in (
                    booking.applicant_telegram_username
                    or booking.customer.telegram_username
                    or ""
                ).lower()
                or needle
                in booking_public_number(
                    booking.id
                ).lower()
            )
        ]

    if sort == "oldest":
        bookings.sort(
            key=lambda booking: (
                booking.created_at
                or datetime.min.replace(
                    tzinfo=timezone.utc
                ),
                booking.id,
            )
        )

    elif sort == "name":
        bookings.sort(
            key=lambda booking: (
                booking.customer.full_name
                or ""
            ).lower()
        )

    elif sort == "amount_desc":
        bookings.sort(
            key=lambda booking:
                Decimal(
                    booking.agreed_price
                    or 0
                ),
            reverse=True,
        )

    elif sort == "amount_asc":
        bookings.sort(
            key=lambda booking:
                Decimal(
                    booking.agreed_price
                    or 0
                )
        )

    else:
        bookings.sort(
            key=lambda booking: (
                booking.created_at
                or datetime.min.replace(
                    tzinfo=timezone.utc
                ),
                booking.id,
            ),
            reverse=True,
        )

    rows = []

    for booking in bookings:
        gross_paid = booking_gross_paid_total(
            booking
        )
        refunded = booking_refunded_total(
            booking
        )
        paid = booking_paid_total(
            booking
        )

        remaining = max(
            Decimal(
                booking.agreed_price
                or 0
            )
            - paid,
            Decimal("0"),
        )

        rows.append(
            {
                "booking": booking,
                "paid": paid,
                "gross_paid": gross_paid,
                "refunded": refunded,
                "remaining": remaining,
            }
        )

    return (
        request.app.state.templates
        .TemplateResponse(
            request=request,
            name="bookings.html",
            context={
                "rows": rows,
                "statuses":
                    BOOKING_STATUSES,
                "departures":
                    departures,
                "q": q,
                "selected_status":
                    status,
                "selected_departure_id":
                    selected_departure_id,
                "selected_sort":
                    sort,
                "format_money":
                    format_money,
                "payment_refunded_total":
                    payment_refunded_total,
                "booking_public_number":
                    booking_public_number,
            },
        )
    )



@router.get(
    "/departures/{departure_id}/export.xlsx"
)
async def export_departure_xlsx(
    departure_id: int,
):
    async with SessionLocal() as session:
        departure = await get_departure(
            session,
            departure_id,
        )

        if departure is None:
            return HTMLResponse(
                "Тур не найден",
                status_code=404,
            )

        await ensure_participants(
            session,
            departure,
        )

        departure = await get_departure(
            session,
            departure_id,
        )

        xlsx_buffer = build_departure_xlsx(
            departure
        )

    filename = (
        f"wowdertour_departure_{departure.id}_"
        f"{departure.start_date.isoformat()}.xlsx"
    )

    return StreamingResponse(
        xlsx_buffer,
        media_type=(
            "application/vnd.openxmlformats-"
            "officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        },
    )


@router.get(
    "/departures/{departure_id}",
    response_class=HTMLResponse,
)
async def departure_page(
    request: Request,
    departure_id: int,
):
    async with SessionLocal() as session:
        departure = await get_departure(
            session,
            departure_id,
        )

        if departure is None:
            return HTMLResponse(
                "Тур не найден",
                status_code=404,
            )

        await ensure_participants(
            session,
            departure,
        )

        departure = await get_departure(
            session,
            departure_id,
        )

        bookings_data = []

        sorted_bookings = sorted(
            departure.bookings,
            key=lambda booking: (
                booking.created_at
                or datetime.min.replace(
                    tzinfo=timezone.utc
                ),
                booking.id,
            ),
            reverse=True,
        )

        for booking in sorted_bookings:
            paid = booking_paid_total(
                booking
            )

            remaining = max(
                booking.agreed_price
                - paid,
                Decimal("0"),
            )

            bookings_data.append(
                {
                    "booking":
                        booking,
                    "paid":
                        paid,
                    "remaining":
                        remaining,
                }
            )

        people_count = (
            departure_reserved_places(
                departure
            )
        )

        room_cards = build_room_cards(
            departure
        )

        total_room_capacity = sum(
            room.capacity or 0
            for room
            in departure.rooms
        )

        occupied_room_beds = sum(
            card["occupied_beds"]
            for card
            in room_cards
        )

        settled_people = sum(
            1
            for booking
            in departure.bookings
            if booking_reserves_places(
                booking
            )
            for participant
            in booking.participants
            if participant.room_id
            is not None
        )

        unsettled_people = max(
            people_count
            - settled_people,
            0,
        )

    return (
        request.app.state.templates
        .TemplateResponse(
            request=request,
            name="departure.html",
            context={
                "departure":
                    departure,
                "bookings_data":
                    bookings_data,
                "people_count":
                    people_count,
                "free_places":
                    max(
                        departure.capacity
                        - people_count,
                        0,
                    ),
                "format_money":
                    format_money,
                "payment_refunded_total":
                    payment_refunded_total,
                "booking_public_number":
                    booking_public_number,
                "statuses":
                    BOOKING_STATUSES,
                "room_cards":
                    room_cards,
                "rooms":
                    sorted(
                        departure.rooms,
                        key=lambda room:
                            natural_text_key(
                                room.number
                            ),
                    ),
                "rates_sorted":
                    sorted(
                        departure.accommodation_rates,
                        key=lambda rate: (
                            not rate.active,
                            rate.title.lower(),
                            rate.id,
                        ),
                    ),
                "total_room_capacity":
                    total_room_capacity,
                "occupied_room_beds":
                    occupied_room_beds,
                "settled_people":
                    settled_people,
                "unsettled_people":
                    unsettled_people,
            },
        )
    )



@router.get(
    "/bookings/{booking_id}",
    response_class=HTMLResponse,
)
async def booking_page(
    request: Request,
    booking_id: int,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Booking)
            .options(
                selectinload(
                    Booking.customer
                ),
                selectinload(
                    Booking.departure
                ).selectinload(
                    TourDeparture.tour
                ),
                selectinload(
                    Booking.departure
                ).selectinload(
                    TourDeparture.accommodation_rates
                ),
                selectinload(
                    Booking.departure
                ).selectinload(
                    TourDeparture.rooms
                ),
                selectinload(
                    Booking.payments
                ).selectinload(
                    Payment.refunds
                ),
                selectinload(
                    Booking.participants
                ).selectinload(
                    Participant.room
                ),
                selectinload(
                    Booking.participants
                ).selectinload(
                    Participant.accommodation_rate
                ),
            )
            .where(
                Booking.id == booking_id
            )
        )

        booking = (
            result.scalars()
            .unique()
            .one_or_none()
        )

        if booking is None:
            return HTMLResponse(
                "Заявка не найдена",
                status_code=404,
            )

        gross_paid = booking_gross_paid_total(
            booking
        )
        refunded = booking_refunded_total(
            booking
        )
        paid = booking_paid_total(
            booking
        )

        remaining = max(
            Decimal(
                booking.agreed_price or 0
            ) - paid,
            Decimal("0"),
        )

        reserves_places = (
            booking_reserves_places(
                booking
            )
        )

    return (
        request.app.state.templates
        .TemplateResponse(
            request=request,
            name="booking.html",
            context={
                "booking": booking,
                "paid": paid,
                "gross_paid": gross_paid,
                "refunded": refunded,
                "remaining": remaining,
                "reserves_places":
                    reserves_places,
                "statuses":
                    BOOKING_STATUSES,
                "format_money":
                    format_money,
                "payment_refunded_total":
                    payment_refunded_total,
                "booking_public_number":
                    booking_public_number,
                "rooms":
                    booking.departure.rooms,
            },
        )
    )


@router.get(
    "/departures/{departure_id}/add-client",
    response_class=HTMLResponse,
)
async def add_client_page(
    request: Request,
    departure_id: int,
):
    async with SessionLocal() as session:
        departure = await get_departure(
            session,
            departure_id,
        )

        if departure is None:
            return HTMLResponse(
                "Тур не найден",
                status_code=404,
            )

    return (
        request.app.state.templates
        .TemplateResponse(
            request=request,
            name="add_client.html",
            context={
                "departure":
                    departure,
                "format_money":
                    format_money,
                "payment_refunded_total":
                    payment_refunded_total,
                "booking_public_number":
                    booking_public_number,
                "statuses":
                    BOOKING_STATUSES,
            },
        )
    )


@router.post(
    "/departures/{departure_id}/add-client"
)
async def add_client(
    departure_id: int,
    full_name: str = Form(...),
    phone: str = Form(""),
    telegram_username: str = Form(""),
    people_count: int = Form(1),
    paid_amount: str = Form("0"),
    comment: str = Form(""),
):
    async with SessionLocal() as session:
        departure = await get_departure(
            session,
            departure_id,
        )

        if departure is None:
            return HTMLResponse(
                "Тур не найден",
                status_code=404,
            )

        if people_count < 1:
            return HTMLResponse(
                "Количество человек "
                "должно быть больше 0",
                status_code=400,
            )

        try:
            calculated_price = (
                Decimal(departure.price)
                * people_count
            )
            total_price = calculated_price

            paid = Decimal(
                paid_amount
                .replace(" ", "")
                .replace(",", ".")
            )

        except InvalidOperation:
            return HTMLResponse(
                "Некорректная сумма",
                status_code=400,
            )

        if paid < 0:
            return HTMLResponse(
                "Сумма не может быть "
                "отрицательной",
                status_code=400,
            )

        if paid <= 0:
            status = "Новая"
        elif paid < total_price:
            status = "Предоплата"
        else:
            status = "Оплачено"

        # Если сразу вносим оплату — блокируем поездку и
        # проверяем актуальную вместимость по оплаченным.
        if paid > 0:
            await session.execute(
                select(TourDeparture.id)
                .where(
                    TourDeparture.id == departure_id
                )
                .with_for_update()
            )

            departure = await get_departure(
                session,
                departure_id,
            )

            occupied = (
                departure_reserved_places(
                    departure
                )
            )

            if (
                occupied + people_count
                > departure.capacity
            ):
                return HTMLResponse(
                    "Недостаточно свободных мест "
                    "для подтверждённой оплаты",
                    status_code=400,
                )

        customer = Customer(
            telegram_id=None,
            telegram_username=(
                telegram_username
                .strip()
                .lstrip("@")
                or None
            ),
            full_name=full_name.strip(),
            phone=(
                phone.strip()
                or None
            ),
            source="manual",
        )

        session.add(customer)
        await session.flush()

        manual_price = None

        booking = Booking(
            customer_id=customer.id,
            departure_id=departure.id,
            status=status,
            people_count=people_count,
            applicant_full_name=full_name.strip(),
            applicant_phone=(
                phone.strip()
                or None
            ),
            applicant_telegram_username=(
                telegram_username
                .strip()
                .lstrip("@")
                or None
            ),
            applicant_telegram_id=None,
            agreed_price=total_price,
            calculated_price=(
                calculated_price
            ),
            manual_price=manual_price,
            price_comment=None,
            comment=(
                comment.strip()
                or None
            ),
            source="manual",
        )

        session.add(booking)
        await session.flush()


        for index in range(
            people_count
        ):
            participant_name = (
                full_name.strip()
                if index == 0
                else f"Участник {index + 1}"
            )

            participant = Participant(
                booking_id=booking.id,
                full_name=participant_name,
                ticket_status="Не куплен",
                occupied_beds=1,
            )

            session.add(participant)

        if paid > 0:
            session.add(
                Payment(
                    booking_id=booking.id,
                    amount=paid,
                    status="paid",
                    payment_type="manual",
                    provider="Не указан",
                    comment=(
                        "Внесено при "
                        "ручном добавлении"
                    ),
                    paid_at=datetime.now(
                        timezone.utc
                    ),
                )
            )

        await sync_booking_payment_status(
            session,
            booking,
        )

        await session.commit()

    return RedirectResponse(
        url=(
            f"/departures/"
            f"{departure_id}"
        ),
        status_code=303,
    )



@router.post(
    "/bookings/{booking_id}/update"
)
async def update_booking(
    booking_id: int,
    status: str = Form(...),
    comment: str = Form(""),
    return_to: str = Form(""),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Booking)
            .options(
                selectinload(Booking.payments)
                .selectinload(Payment.refunds)
            )
            .where(
                Booking.id == booking_id
            )
        )

        booking = result.scalar_one_or_none()

        if booking is None:
            return HTMLResponse(
                "Заявка не найдена",
                status_code=404,
            )

        if status not in BOOKING_STATUSES:
            return HTMLResponse(
                "Некорректный статус",
                status_code=400,
            )

        if (
            status == "Не актуальна"
            and booking_gross_paid_total(booking) > 0
        ):
            return HTMLResponse(
                (
                    "Нельзя поставить статус «Не актуальна»: "
                    "по заявке уже было поступление денег. "
                    "Используйте статус «Отмена» и при необходимости "
                    "оформите возврат платежа."
                ),
                status_code=400,
            )

        booking.status = status
        booking.comment = (
            comment.strip()
            or None
        )

        if status not in CLOSED_BOOKING_STATUSES:
            await sync_booking_payment_status(
                session,
                booking,
            )

        departure_id = booking.departure_id

        await session.commit()

    target = (
        return_to.strip()
        or f"/departures/{departure_id}"
    )

    return RedirectResponse(
        url=target,
        status_code=303,
    )


@router.post(
    "/bookings/{booking_id}/close-unpaid"
)
async def close_unpaid_booking(
    booking_id: int,
    return_to: str = Form(""),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Booking)
            .options(
                selectinload(
                    Booking.payments
                )
            )
            .where(
                Booking.id == booking_id
            )
        )

        booking = (
            result.scalar_one_or_none()
        )

        if booking is None:
            return HTMLResponse(
                "Заявка не найдена",
                status_code=404,
            )

        paid_total = booking_gross_paid_total(
            booking
        )

        if paid_total > 0:
            return HTMLResponse(
                (
                    "Нельзя закрыть заявку "
                    "как неоплаченную: "
                    "по ней уже есть платёж."
                ),
                status_code=400,
            )

        booking.status = "Не актуальна"

        departure_id = (
            booking.departure_id
        )

        await session.commit()

    target = (
        return_to.strip()
        or f"/departures/{departure_id}"
    )

    return RedirectResponse(
        url=target,
        status_code=303,
    )


@router.post(
    "/bookings/{booking_id}/payments/add"
)
async def add_booking_payment(
    booking_id: int,
    amount: str = Form(...),
    payment_method: str = Form("Перевод"),
    payment_date: str = Form(""),
    payment_comment: str = Form(""),
    return_to: str = Form(""),
):
    try:
        payment_amount = Decimal(
            amount
            .replace(" ", "")
            .replace(",", ".")
        )
    except InvalidOperation:
        return HTMLResponse(
            "Некорректная сумма платежа",
            status_code=400,
        )

    if payment_amount <= 0:
        return HTMLResponse(
            "Сумма платежа должна быть больше 0",
            status_code=400,
        )

    payment_method = (
        payment_method.strip()
        or "Не указан"
    )

    paid_at = datetime.now(
        timezone.utc
    )

    if payment_date.strip():
        try:
            chosen_date = date.fromisoformat(
                payment_date.strip()
            )
        except ValueError:
            return HTMLResponse(
                "Некорректная дата платежа",
                status_code=400,
            )

        paid_at = datetime.combine(
            chosen_date,
            time(hour=12),
            tzinfo=timezone.utc,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(Booking)
            .options(
                selectinload(Booking.payments)
                .selectinload(Payment.refunds)
            )
            .where(
                Booking.id == booking_id
            )
        )

        booking = result.scalar_one_or_none()

        if booking is None:
            return HTMLResponse(
                "Заявка не найдена",
                status_code=404,
            )

        if booking.status in CLOSED_BOOKING_STATUSES:
            return HTMLResponse(
                (
                    "Нельзя добавить платёж к закрытой заявке. "
                    "Сначала верните её в рабочий статус."
                ),
                status_code=400,
            )

        await session.execute(
            select(TourDeparture.id)
            .where(
                TourDeparture.id == booking.departure_id
            )
            .with_for_update()
        )

        if booking.status != "Отмена":
            departure = await get_departure(
                session,
                booking.departure_id,
            )

            occupied = (
                departure_reserved_places(
                    departure
                )
            )

            already_reserved = (
                booking_reserves_places(
                    booking
                )
            )

            needed_places = (
                0
                if already_reserved
                else booking.people_count
            )

            if (
                occupied + needed_places
                > departure.capacity
            ):
                return HTMLResponse(
                    (
                        "Платёж нельзя добавить: "
                        "на поездке уже недостаточно "
                        "свободных мест."
                    ),
                    status_code=400,
                )

        payment = Payment(
            booking_id=booking.id,
            amount=payment_amount,
            status="paid",
            payment_type="manual",
            provider=payment_method,
            comment=(
                payment_comment.strip()
                or None
            ),
            paid_at=paid_at,
        )

        session.add(payment)

        await sync_booking_payment_status(
            session,
            booking,
        )

        departure_id = booking.departure_id

        await session.commit()

    target = (
        return_to.strip()
        or f"/departures/{departure_id}"
    )

    return RedirectResponse(
        url=target,
        status_code=303,
    )


@router.post(
    "/payments/{payment_id}/cancel"
)
async def cancel_booking_payment(
    payment_id: int,
    return_to: str = Form(""),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Payment)
            .options(
                selectinload(Payment.booking),
                selectinload(Payment.refunds),
            )
            .where(
                Payment.id == payment_id
            )
        )

        payment = result.scalar_one_or_none()

        if payment is None:
            return HTMLResponse(
                "Платёж не найден",
                status_code=404,
            )

        if payment.payment_type != "manual":
            return HTMLResponse(
                "Автоматический платёж "
                "нельзя отменить вручную",
                status_code=400,
            )

        if payment_refunded_total(payment) > 0:
            return HTMLResponse(
                (
                    "Нельзя отменить платёж, по которому уже оформлен "
                    "возврат. Если возврат был внесён ошибочно, сначала "
                    "отмените запись возврата."
                ),
                status_code=400,
            )

        payment.status = "cancelled"

        await sync_booking_payment_status(
            session,
            payment.booking,
        )

        departure_id = (
            payment.booking.departure_id
        )

        await session.commit()

    target = (
        return_to.strip()
        or f"/departures/{departure_id}"
    )

    return RedirectResponse(
        url=target,
        status_code=303,
    )



@router.post(
    "/payments/{payment_id}/refunds/add"
)
async def add_payment_refund(
    payment_id: int,
    amount: str = Form(...),
    refund_method: str = Form("Перевод"),
    refund_date: str = Form(""),
    refund_comment: str = Form(""),
    return_to: str = Form(""),
):
    try:
        refund_amount = Decimal(
            amount.replace(" ", "").replace(",", ".")
        )
    except InvalidOperation:
        return HTMLResponse(
            "Некорректная сумма возврата",
            status_code=400,
        )

    if refund_amount <= 0:
        return HTMLResponse(
            "Сумма возврата должна быть больше 0",
            status_code=400,
        )

    refunded_at = datetime.now(timezone.utc)
    if refund_date.strip():
        try:
            chosen_date = date.fromisoformat(refund_date.strip())
        except ValueError:
            return HTMLResponse(
                "Некорректная дата возврата",
                status_code=400,
            )
        refunded_at = datetime.combine(
            chosen_date, time(hour=12), tzinfo=timezone.utc
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(Payment)
            .options(
                selectinload(Payment.refunds),
                selectinload(Payment.booking),
            )
            .where(Payment.id == payment_id)
            .with_for_update()
        )
        payment = result.scalars().unique().one_or_none()

        if payment is None:
            return HTMLResponse("Платёж не найден", status_code=404)

        if payment.status not in SUCCESS_PAYMENT_STATUSES:
            return HTMLResponse(
                "Возврат можно оформить только по успешному платежу",
                status_code=400,
            )

        already_refunded = payment_refunded_total(payment)
        refundable = max(
            Decimal(payment.amount) - already_refunded,
            Decimal("0"),
        )

        if refund_amount > refundable:
            return HTMLResponse(
                (
                    "Сумма возврата превышает доступный остаток. "
                    f"Можно вернуть не больше {format_money(refundable)} ₽."
                ),
                status_code=400,
            )

        refund = PaymentRefund(
            payment_id=payment.id,
            amount=refund_amount,
            status="succeeded",
            refund_method=(refund_method.strip() or "Не указан"),
            comment=(refund_comment.strip() or None),
            refunded_at=refunded_at,
        )
        session.add(refund)

        await sync_booking_payment_status(
            session, payment.booking
        )
        departure_id = payment.booking.departure_id
        await session.commit()

    target = return_to.strip() or f"/departures/{departure_id}"
    return RedirectResponse(url=target, status_code=303)


@router.post(
    "/refunds/{refund_id}/cancel"
)
async def cancel_payment_refund(
    refund_id: int,
    return_to: str = Form(""),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(PaymentRefund)
            .options(
                selectinload(PaymentRefund.payment)
                .selectinload(Payment.booking)
            )
            .where(PaymentRefund.id == refund_id)
        )
        refund = result.scalars().unique().one_or_none()

        if refund is None:
            return HTMLResponse("Возврат не найден", status_code=404)

        if refund.status != "succeeded":
            return HTMLResponse(
                "Этот возврат уже отменён",
                status_code=400,
            )

        refund.status = "cancelled"
        await sync_booking_payment_status(
            session, refund.payment.booking
        )
        departure_id = refund.payment.booking.departure_id
        await session.commit()

    target = return_to.strip() or f"/departures/{departure_id}"
    return RedirectResponse(url=target, status_code=303)
