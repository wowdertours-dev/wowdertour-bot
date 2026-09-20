from decimal import Decimal, InvalidOperation
import re
from uuid import uuid4

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.crm.pricing import (
    calculate_booking_price,
    sync_booking_payment_status,
)
from app.database.models import (
    AccommodationRate,
    Booking,
    Participant,
    Payment,
    Room,
    TourDeparture,
)
from app.database.session import SessionLocal


router = APIRouter()



async def load_booking(
    session,
    booking_id: int,
):
    result = await session.execute(
        select(Booking)
        .options(
            selectinload(Booking.departure),
            selectinload(Booking.payments)
            .selectinload(Payment.refunds),
            selectinload(Booking.participants)
            .selectinload(Participant.accommodation_rate),
        )
        .where(Booking.id == booking_id)
    )

    return result.scalar_one_or_none()


async def recalculate_booking(
    session,
    booking_id: int,
):
    booking = await load_booking(
        session,
        booking_id,
    )

    if booking is None:
        return

    calculated_price = calculate_booking_price(
        booking
    )

    booking.calculated_price = calculated_price

    if booking.manual_price is None:
        booking.agreed_price = calculated_price

    await sync_booking_payment_status(booking)


def _placement_size(value: str | None) -> int | None:
    """
    Extract the first seat count from labels such as
    '2-местная', '2-местное', '3 местная'.
    """
    if not value:
        return None

    match = re.search(r"\d+", value)
    if not match:
        return None

    return int(match.group())


def room_matches_participant_accommodation(
    room: Room,
    participant: Participant,
) -> bool:
    """
    If both room type and accommodation title contain a seat count,
    require them to match. If the room type has no numeric size,
    do not guess and allow the participant; capacity is still checked.
    """
    room_size = _placement_size(room.room_type)
    accommodation_size = _placement_size(
        participant.accommodation_type
    )

    if room_size is None:
        return True

    if accommodation_size is None:
        return False

    return room_size == accommodation_size


def get_room_occupied_beds(
    room: Room,
    *,
    exclude_participant_id: int | None = None,
) -> int:
    occupied = 0

    for participant in room.participants:
        if (
            exclude_participant_id is not None
            and participant.id
            == exclude_participant_id
        ):
            continue

        occupied += participant.occupied_beds

    return occupied



@router.post(
    "/departures/{departure_id}/accommodation-rates/add"
)
async def add_accommodation_rate(
    departure_id: int,
    title: str = Form(...),
    price_per_person: str = Form(...),
    occupied_beds: int = Form(1),
):
    title = title.strip()

    if not title:
        return HTMLResponse(
            "Укажите название тарифа",
            status_code=400,
        )

    try:
        price = Decimal(
            price_per_person
            .replace(" ", "")
            .replace(",", ".")
        )
    except InvalidOperation:
        return HTMLResponse(
            "Некорректная стоимость тарифа",
            status_code=400,
        )

    if price < 0:
        return HTMLResponse(
            "Стоимость не может быть отрицательной",
            status_code=400,
        )

    if occupied_beds < 1:
        return HTMLResponse(
            "Количество занимаемых мест должно быть больше 0",
            status_code=400,
        )

    async with SessionLocal() as session:
        departure_result = await session.execute(
            select(TourDeparture)
            .where(
                TourDeparture.id == departure_id
            )
        )

        departure = (
            departure_result.scalar_one_or_none()
        )

        if departure is None:
            return HTMLResponse(
                "Тур не найден",
                status_code=404,
            )

        rate = AccommodationRate(
            departure_id=departure_id,
            code=f"rate_{uuid4().hex[:12]}",
            title=title,
            price_per_person=price,
            occupied_beds=occupied_beds,
            active=True,
        )

        session.add(rate)
        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}",
        status_code=303,
    )


@router.post(
    "/accommodation-rates/{rate_id}/update"
)
async def update_accommodation_rate(
    rate_id: int,
    title: str = Form(...),
    price_per_person: str = Form(...),
    occupied_beds: int = Form(1),
):
    title = title.strip()

    if not title:
        return HTMLResponse(
            "Укажите название тарифа",
            status_code=400,
        )

    try:
        price = Decimal(
            price_per_person
            .replace(" ", "")
            .replace(",", ".")
        )
    except InvalidOperation:
        return HTMLResponse(
            "Некорректная стоимость тарифа",
            status_code=400,
        )

    if price < 0:
        return HTMLResponse(
            "Стоимость не может быть отрицательной",
            status_code=400,
        )

    if occupied_beds < 1:
        return HTMLResponse(
            "Количество занимаемых мест должно быть больше 0",
            status_code=400,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(AccommodationRate)
            .where(
                AccommodationRate.id == rate_id
            )
        )

        rate = result.scalar_one_or_none()

        if rate is None:
            return HTMLResponse(
                "Тариф не найден",
                status_code=404,
            )

        departure_id = rate.departure_id

        rate.title = title
        rate.price_per_person = price
        rate.occupied_beds = occupied_beds

        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}",
        status_code=303,
    )


@router.post(
    "/accommodation-rates/{rate_id}/toggle"
)
async def toggle_accommodation_rate(
    rate_id: int,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(AccommodationRate)
            .where(
                AccommodationRate.id == rate_id
            )
        )

        rate = result.scalar_one_or_none()

        if rate is None:
            return HTMLResponse(
                "Тариф не найден",
                status_code=404,
            )

        departure_id = rate.departure_id
        rate.active = not rate.active

        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}",
        status_code=303,
    )


@router.post(
    "/accommodation-rates/{rate_id}/delete"
)
async def delete_accommodation_rate(
    rate_id: int,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(AccommodationRate)
            .where(
                AccommodationRate.id == rate_id
            )
        )

        rate = result.scalar_one_or_none()

        if rate is None:
            return HTMLResponse(
                "Тариф не найден",
                status_code=404,
            )

        departure_id = rate.departure_id

        participant_result = await session.execute(
            select(Participant.id)
            .where(
                Participant.accommodation_rate_id
                == rate_id
            )
            .limit(1)
        )

        if (
            participant_result.scalar_one_or_none()
            is not None
        ):
            return HTMLResponse(
                "Нельзя удалить тариф: "
                "он уже назначен участнику. "
                "Сначала уберите тариф у участника "
                "или просто скройте его.",
                status_code=400,
            )

        await session.delete(rate)
        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}",
        status_code=303,
    )


@router.post(
    "/departures/{departure_id}/rooms/add"
)
async def add_room(
    departure_id: int,
    number: str = Form(...),
    room_type: str = Form(...),
    capacity: int = Form(...),
    notes: str = Form(""),
):
    number = number.strip()
    room_type = room_type.strip()

    if not number:
        return HTMLResponse(
            "Укажите номер комнаты",
            status_code=400,
        )

    if capacity < 1:
        return HTMLResponse(
            "Вместимость комнаты должна быть больше 0",
            status_code=400,
        )

    async with SessionLocal() as session:
        departure_result = (
            await session.execute(
                select(TourDeparture)
                .where(
                    TourDeparture.id
                    == departure_id
                )
            )
        )

        departure = (
            departure_result
            .scalar_one_or_none()
        )

        if departure is None:
            return HTMLResponse(
                "Тур не найден",
                status_code=404,
            )

        existing_result = (
            await session.execute(
                select(Room)
                .where(
                    Room.departure_id
                    == departure_id,
                    Room.number
                    == number,
                )
            )
        )

        if (
            existing_result
            .scalar_one_or_none()
            is not None
        ):
            return HTMLResponse(
                "Комната с таким номером уже существует",
                status_code=400,
            )

        room = Room(
            departure_id=departure_id,
            number=number,
            room_type=room_type,
            capacity=capacity,
            notes=notes.strip() or None,
        )

        session.add(room)

        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}",
        status_code=303,
    )


@router.post(
    "/rooms/{room_id}/delete"
)
async def delete_room(
    room_id: int,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Room)
            .options(
                selectinload(
                    Room.participants
                )
            )
            .where(
                Room.id == room_id
            )
        )

        room = result.scalar_one_or_none()

        if room is None:
            return HTMLResponse(
                "Комната не найдена",
                status_code=404,
            )

        departure_id = (
            room.departure_id
        )

        if room.participants:
            return HTMLResponse(
                "Нельзя удалить комнату: "
                "в ней уже есть участники",
                status_code=400,
            )

        await session.delete(room)
        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}",
        status_code=303,
    )


@router.post(
    "/rooms/{room_id}/participants/assign"
)
async def assign_participant_to_room(
    room_id: int,
    participant_id: int = Form(...),
):
    async with SessionLocal() as session:
        room_result = await session.execute(
            select(Room)
            .options(
                selectinload(Room.participants),
            )
            .where(Room.id == room_id)
        )

        room = room_result.scalar_one_or_none()

        if room is None:
            return HTMLResponse(
                "Комната не найдена",
                status_code=404,
            )

        participant_result = await session.execute(
            select(Participant)
            .options(
                selectinload(Participant.booking),
                selectinload(
                    Participant.accommodation_rate
                ),
            )
            .where(Participant.id == participant_id)
        )

        participant = (
            participant_result.scalar_one_or_none()
        )

        if participant is None:
            return HTMLResponse(
                "Участник не найден",
                status_code=404,
            )

        if (
            participant.booking.departure_id
            != room.departure_id
        ):
            return HTMLResponse(
                "Участник относится к другому выезду",
                status_code=400,
            )

        if participant.booking.status in {
            "Отмена",
            "Не актуальна",
        }:
            return HTMLResponse(
                "Нельзя заселить участника "
                "из закрытой заявки",
                status_code=400,
            )

        if participant.room_id is not None:
            return HTMLResponse(
                "Этот участник уже заселён "
                "в комнату",
                status_code=400,
            )

        if participant.accommodation_rate_id is None:
            return HTMLResponse(
                "Сначала выберите участнику "
                "тип размещения",
                status_code=400,
            )

        if not room_matches_participant_accommodation(
            room,
            participant,
        ):
            return HTMLResponse(
                "Тип размещения участника "
                "не подходит этой комнате",
                status_code=400,
            )

        occupied = get_room_occupied_beds(room)

        if (
            occupied + participant.occupied_beds
            > (room.capacity or 0)
        ):
            return HTMLResponse(
                "В комнате недостаточно "
                "свободных мест",
                status_code=400,
            )

        participant.room_id = room.id

        await session.commit()

    return RedirectResponse(
        url=f"/departures/{room.departure_id}",
        status_code=303,
    )


@router.post(
    "/participants/{participant_id}/room/replace"
)
async def replace_room_participant(
    participant_id: int,
    replacement_participant_id: int = Form(...),
):
    async with SessionLocal() as session:
        target_result = await session.execute(
            select(Participant)
            .options(
                selectinload(Participant.booking),
                selectinload(Participant.room)
                .selectinload(Room.participants),
                selectinload(
                    Participant.accommodation_rate
                ),
            )
            .where(
                Participant.id == participant_id
            )
        )

        target = target_result.scalar_one_or_none()

        if target is None:
            return HTMLResponse(
                "Участник не найден",
                status_code=404,
            )

        if target.room is None:
            return HTMLResponse(
                "Участник не заселён в комнату",
                status_code=400,
            )

        if target.accommodation_rate_id is None:
            return HTMLResponse(
                "У участника не выбран тип размещения",
                status_code=400,
            )

        replacement_result = await session.execute(
            select(Participant)
            .options(
                selectinload(Participant.booking),
                selectinload(
                    Participant.accommodation_rate
                ),
            )
            .where(
                Participant.id
                == replacement_participant_id
            )
        )

        replacement = (
            replacement_result.scalar_one_or_none()
        )

        if replacement is None:
            return HTMLResponse(
                "Участник для замены не найден",
                status_code=404,
            )

        if replacement.id == target.id:
            return HTMLResponse(
                "Нельзя заменить участника им же самим",
                status_code=400,
            )

        departure_id = target.booking.departure_id

        if (
            replacement.booking.departure_id
            != departure_id
        ):
            return HTMLResponse(
                "Участник относится к другому выезду",
                status_code=400,
            )

        if replacement.booking.status in {
            "Отмена",
            "Не актуальна",
        }:
            return HTMLResponse(
                "Нельзя заселить участника "
                "из закрытой заявки",
                status_code=400,
            )

        if replacement.room_id is not None:
            return HTMLResponse(
                "Этот участник уже заселён "
                "в другую комнату",
                status_code=400,
            )

        # Замена разрешена только внутри одного и того же
        # тарифа/типа размещения. Например, участника с
        # «2-местным» размещением можно заменить только
        # другим участником с тем же тарифом.
        if (
            replacement.accommodation_rate_id
            != target.accommodation_rate_id
        ):
            return HTMLResponse(
                "Тип размещения участников "
                "не совпадает",
                status_code=400,
            )

        room = target.room

        occupied_without_target = (
            get_room_occupied_beds(
                room,
                exclude_participant_id=target.id,
            )
        )

        if (
            occupied_without_target
            + replacement.occupied_beds
            > (room.capacity or 0)
        ):
            return HTMLResponse(
                "В комнате недостаточно "
                "свободных мест",
                status_code=400,
            )

        target.room_id = None
        replacement.room_id = room.id

        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}",
        status_code=303,
    )


@router.post(
    "/participants/{participant_id}/room/remove"
)
async def remove_room_participant(
    participant_id: int,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Participant)
            .options(
                selectinload(Participant.booking)
            )
            .where(
                Participant.id == participant_id
            )
        )

        participant = result.scalar_one_or_none()

        if participant is None:
            return HTMLResponse(
                "Участник не найден",
                status_code=404,
            )

        departure_id = (
            participant.booking.departure_id
        )

        if participant.room_id is None:
            return HTMLResponse(
                "Участник уже не расселён",
                status_code=400,
            )

        participant.room_id = None

        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}",
        status_code=303,
    )


@router.post(
    "/participants/{participant_id}/accommodation"
)
async def update_participant_accommodation(
    participant_id: int,
    full_name: str = Form(...),
    accommodation_rate_id: str = Form(""),
    room_id: str = Form(""),
    ticket_status: str = Form("Не куплен"),
    participant_comment: str = Form(""),
    return_to: str = Form(""),
):
    async with SessionLocal() as session:
        participant_result = (
            await session.execute(
                select(Participant)
                .options(
                    selectinload(
                        Participant.booking
                    ),
                    selectinload(
                        Participant.room
                    ),
                )
                .where(
                    Participant.id
                    == participant_id
                )
            )
        )

        participant = (
            participant_result
            .scalar_one_or_none()
        )

        if participant is None:
            return HTMLResponse(
                "Участник не найден",
                status_code=404,
            )

        departure_id = (
            participant.booking.departure_id
        )

        participant.full_name = (
            full_name.strip()
        )

        participant.ticket_status = (
            ticket_status
        )

        participant.comment = (
            participant_comment.strip()
            or None
        )

        selected_rate = None

        if accommodation_rate_id:
            try:
                rate_id = int(
                    accommodation_rate_id
                )
            except ValueError:
                return HTMLResponse(
                    "Некорректный тариф",
                    status_code=400,
                )

            rate_result = (
                await session.execute(
                    select(AccommodationRate)
                    .where(
                        AccommodationRate.id
                        == rate_id,
                        AccommodationRate.departure_id
                        == departure_id,
                        AccommodationRate.active.is_(
                            True
                        ),
                    )
                )
            )

            selected_rate = (
                rate_result
                .scalar_one_or_none()
            )

            if selected_rate is None:
                return HTMLResponse(
                    "Тариф проживания не найден",
                    status_code=404,
                )

        selected_room = None

        if room_id:
            try:
                selected_room_id = int(
                    room_id
                )
            except ValueError:
                return HTMLResponse(
                    "Некорректная комната",
                    status_code=400,
                )

            room_result = (
                await session.execute(
                    select(Room)
                    .options(
                        selectinload(
                            Room.participants
                        )
                    )
                    .where(
                        Room.id
                        == selected_room_id,
                        Room.departure_id
                        == departure_id,
                    )
                )
            )

            selected_room = (
                room_result
                .scalar_one_or_none()
            )

            if selected_room is None:
                return HTMLResponse(
                    "Комната не найдена",
                    status_code=404,
                )

        if (
            selected_room is not None
            and selected_rate is None
        ):
            return HTMLResponse(
                "Сначала выберите вариант размещения",
                status_code=400,
            )

        if (
            selected_rate is not None
            and selected_room is not None
        ):
            required_beds = (
                selected_rate.occupied_beds
            )

            occupied_beds = (
                get_room_occupied_beds(
                    selected_room,
                    exclude_participant_id=(
                        participant.id
                    ),
                )
            )

            room_capacity = (
                selected_room.capacity
                or 0
            )

            if (
                occupied_beds
                + required_beds
                > room_capacity
            ):
                return HTMLResponse(
                    "В комнате недостаточно "
                    "свободных мест",
                    status_code=400,
                )

        participant.accommodation_rate_id = (
            selected_rate.id
            if selected_rate
            else None
        )

        participant.accommodation_type = (
            selected_rate.title
            if selected_rate
            else None
        )

        participant.accommodation_price = (
            selected_rate.price_per_person
            if selected_rate
            else None
        )

        participant.occupied_beds = (
            selected_rate.occupied_beds
            if selected_rate
            else 1
        )

        participant.room_id = (
            selected_room.id
            if selected_room
            else None
        )

        await session.flush()

        await recalculate_booking(
            session,
            participant.booking_id,
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