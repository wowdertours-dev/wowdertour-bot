from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import (
    Booking,
    Participant,
    Payment,
    PaymentRefund,
)
from app.database.session import SessionLocal


router = APIRouter()


def calculate_booking_price(
    booking: Booking,
) -> Decimal:
    """
    Автоматическая стоимость заявки.

    Если у участника выбран тариф проживания,
    берём зафиксированную стоимость участника.
    Если тариф не выбран — используем базовую
    цену выезда.

    Если участников ещё нет, считаем:
    базовая цена × количество человек.
    """
    base_price = Decimal(
        booking.departure.price or 0
    )

    participants = list(
        booking.participants or []
    )

    if not participants:
        return (
            base_price
            * int(booking.people_count or 0)
        )

    total = Decimal("0")

    for participant in participants:
        if (
            participant.accommodation_price
            is not None
        ):
            total += Decimal(
                participant.accommodation_price
            )
        else:
            total += base_price

    return total


async def sync_booking_payment_status(
    booking: Booking,
) -> None:
    """Synchronize status using net payments after successful refunds."""
    if booking.status == "Отмена":
        return

    gross_paid = sum(
        (
            Decimal(payment.amount)
            for payment in booking.payments
            if (
                payment.status in {"paid", "succeeded"}
                and Decimal(payment.amount) > 0
            )
        ),
        Decimal("0"),
    )

    refunded = sum(
        (
            Decimal(refund.amount)
            for payment in booking.payments
            if payment.status in {"paid", "succeeded"}
            for refund in payment.refunds
            if (
                refund.status == "succeeded"
                and Decimal(refund.amount) > 0
            )
        ),
        Decimal("0"),
    )

    paid_total = max(gross_paid - refunded, Decimal("0"))
    total_price = Decimal(booking.agreed_price or 0)

    if total_price > 0 and paid_total >= total_price:
        booking.status = "Оплачено"
    elif paid_total > 0:
        booking.status = "Предоплата"
    elif booking.status in {"Предоплата", "Оплачено"}:
        booking.status = "Связались"


async def get_booking(
    session,
    booking_id: int,
) -> Booking | None:
    result = await session.execute(
        select(Booking)
        .options(
            selectinload(
                Booking.departure
            ),
            selectinload(
                Booking.participants
            ).selectinload(
                Participant.accommodation_rate
            ),
            selectinload(
                Booking.payments
            ).selectinload(
                Payment.refunds
            ),
        )
        .where(
            Booking.id == booking_id
        )
    )

    return result.scalar_one_or_none()


@router.post(
    "/bookings/{booking_id}/price"
)
async def update_booking_price(
    booking_id: int,
    manual_price: str = Form(""),
    price_comment: str = Form(""),
    return_to: str = Form(""),
):
    async with SessionLocal() as session:
        booking = await get_booking(
            session,
            booking_id,
        )

        if booking is None:
            return HTMLResponse(
                "Заявка не найдена",
                status_code=404,
            )

        calculated_price = (
            calculate_booking_price(
                booking
            )
        )

        booking.calculated_price = (
            calculated_price
        )

        value = manual_price.strip()

        if value:
            try:
                new_manual_price = Decimal(
                    value
                    .replace(" ", "")
                    .replace(",", ".")
                )
            except InvalidOperation:
                return HTMLResponse(
                    "Некорректная ручная цена",
                    status_code=400,
                )

            if new_manual_price < 0:
                return HTMLResponse(
                    "Цена не может быть отрицательной",
                    status_code=400,
                )

            booking.manual_price = (
                new_manual_price
            )
            booking.agreed_price = (
                new_manual_price
            )
            booking.price_comment = (
                price_comment.strip()
                or None
            )

        else:
            booking.manual_price = None
            booking.agreed_price = (
                calculated_price
            )
            booking.price_comment = None

        await sync_booking_payment_status(
            booking
        )

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
