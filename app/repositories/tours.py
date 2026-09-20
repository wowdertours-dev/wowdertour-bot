from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import (
    Booking,
    Payment,
    TourCategory,
    TourDeparture,
    TourMedia,
    TourType,
)


def today() -> date:
    return date.today()


def is_departure_finished(
    departure: TourDeparture,
) -> bool:
    return departure.end_date < today()


def is_booking_closed_by_date(
    departure: TourDeparture,
) -> bool:
    return departure.start_date <= today()


async def get_active_categories(
    session,
) -> list[TourCategory]:
    result = await session.execute(
        select(TourCategory)
        .where(
            TourCategory.active.is_(True)
        )
        .order_by(
            TourCategory.sort_order,
            TourCategory.title,
        )
    )

    return list(
        result.scalars().all()
    )


async def get_category_by_slug(
    session,
    slug: str,
) -> TourCategory | None:
    result = await session.execute(
        select(TourCategory)
        .options(
            selectinload(
                TourCategory.media
            )
        )
        .where(
            TourCategory.slug == slug,
            TourCategory.active.is_(True),
        )
    )

    return (
        result.scalars()
        .unique()
        .one_or_none()
    )


async def get_active_tours_by_category(
    session,
    category_id: int,
) -> list[TourType]:
    result = await session.execute(
        select(TourType)
        .options(
            selectinload(
                TourType.category
            )
        )
        .where(
            TourType.category_id
            == category_id,
            TourType.active.is_(True),
        )
        .order_by(
            TourType.title
        )
    )

    return list(
        result.scalars().all()
    )


async def get_active_tours(
    session,
) -> list[TourType]:
    result = await session.execute(
        select(TourType)
        .join(
            TourCategory,
            TourType.category_id
            == TourCategory.id,
        )
        .where(
            TourType.active.is_(True),
            TourCategory.active.is_(True),
        )
        .order_by(
            TourType.title
        )
    )

    return list(
        result.scalars().all()
    )


async def get_tour_by_slug(
    session,
    slug: str,
) -> TourType | None:
    result = await session.execute(
        select(TourType)
        .join(
            TourCategory,
            TourType.category_id
            == TourCategory.id,
        )
        .options(
            selectinload(
                TourType.category
            ),
            selectinload(
                TourType.media
            ),
        )
        .where(
            TourType.slug == slug,
            TourType.active.is_(True),
            TourCategory.active.is_(True),
        )
    )

    return (
        result.scalars()
        .unique()
        .one_or_none()
    )


async def get_active_departures(
    session,
    tour_id: int,
) -> list[TourDeparture]:
    result = await session.execute(
        select(TourDeparture)
        .options(
            selectinload(
                TourDeparture.bookings
            ).selectinload(
                Booking.payments
            ).selectinload(
                Payment.refunds
            )
        )
        .where(
            TourDeparture.tour_id
            == tour_id,
            TourDeparture.active.is_(True),
            TourDeparture.archived.is_(False),
            TourDeparture.end_date
            >= today(),
        )
        .order_by(
            TourDeparture.start_date
        )
    )

    return list(
        result.scalars()
        .unique()
        .all()
    )


async def get_bookable_departures(
    session,
    tour_id: int,
) -> list[TourDeparture]:
    result = await session.execute(
        select(TourDeparture)
        .options(
            selectinload(
                TourDeparture.bookings
            ).selectinload(
                Booking.payments
            ).selectinload(
                Payment.refunds
            )
        )
        .where(
            TourDeparture.tour_id
            == tour_id,
            TourDeparture.active.is_(True),
            TourDeparture.archived.is_(False),
            TourDeparture.booking_open.is_(True),
            TourDeparture.start_date
            > today(),
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

    return [
        departure
        for departure in departures
        if get_free_places(
            departure
        ) > 0
    ]


async def get_departure_by_id(
    session,
    departure_id: int,
) -> TourDeparture | None:
    result = await session.execute(
        select(TourDeparture)
        .options(
            selectinload(
                TourDeparture.tour
            ).selectinload(
                TourType.category
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
            TourDeparture.id
            == departure_id
        )
    )

    return (
        result.scalars()
        .unique()
        .one_or_none()
    )


async def get_about_media(
    session,
) -> list[TourMedia]:
    result = await session.execute(
        select(TourMedia)
        .where(
            TourMedia.category_id.is_(None),
            TourMedia.tour_id.is_(None),
            TourMedia.section == "about",
            TourMedia.active.is_(True),
            TourMedia.media_type == "photo",
        )
        .order_by(
            TourMedia.sort_order,
            TourMedia.id,
        )
    )

    return list(
        result.scalars().all()
    )


def get_occupied_places(
    departure: TourDeparture,
) -> int:
    """
    Для доступности в Telegram место считается
    занятым только после фактической успешной оплаты.

    Неоплаченные, отменённые и неактуальные заявки
    не уменьшают доступную вместимость.
    """
    def net_paid(booking: Booking) -> Decimal:
        gross = sum(
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
        return max(gross - refunded, Decimal("0"))

    return sum(
        booking.people_count
        for booking in departure.bookings
        if (
            booking.status not in {"Отмена", "Не актуальна"}
            and net_paid(booking) > 0
        )
    )


def get_free_places(
    departure: TourDeparture,
) -> int:
    return max(
        departure.capacity
        - get_occupied_places(
            departure
        ),
        0,
    )


def can_book_departure(
    departure: TourDeparture,
    people_count: int = 1,
) -> bool:
    if not departure.active:
        return False

    if departure.archived:
        return False

    if not departure.booking_open:
        return False

    if is_departure_finished(
        departure
    ):
        return False

    if is_booking_closed_by_date(
        departure
    ):
        return False

    if (
        departure.tour
        and not departure.tour.active
    ):
        return False

    if (
        departure.tour
        and departure.tour.category
        and not departure.tour.category.active
    ):
        return False

    return (
        get_free_places(
            departure
        )
        >= people_count
    )