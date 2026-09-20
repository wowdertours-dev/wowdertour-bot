from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import (
    exists,
    func,
    select,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import (
    Booking,
    Customer,
    Participant,
    Payment,
    PaymentRefund,
    TourDeparture,
)


@dataclass
class BookingCreationResult:
    booking: Booking
    departure: TourDeparture
    total_price: Decimal
    free_places: int


class BookingService:
    def __init__(
        self,
        session: AsyncSession,
    ):
        self.session = session

    async def create_booking(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
        full_name: str,
        phone: str,
        departure_id: int,
        people_count: int,
        comment: str | None,
        source: str = "telegram",
    ) -> BookingCreationResult:
        if people_count < 1:
            raise ValueError(
                "Количество человек должно "
                "быть больше нуля."
            )

        try:
            departure = (
                await self._get_locked_departure(
                    departure_id
                )
            )

            if departure is None:
                raise ValueError(
                    "Эта дата больше недоступна."
                )

            if not departure.active:
                raise ValueError(
                    "Этот выезд больше недоступен."
                )

            if departure.archived:
                raise ValueError(
                    "Этот выезд находится в архиве."
                )

            if not departure.booking_open:
                raise ValueError(
                    "Запись на этот выезд закрыта."
                )

            occupied_places = (
                await self._get_occupied_places(
                    departure.id
                )
            )

            free_places = max(
                departure.capacity
                - occupied_places,
                0,
            )

            if free_places <= 0:
                raise ValueError(
                    "На этот выезд больше "
                    "нет свободных мест."
                )

            if people_count > free_places:
                raise ValueError(
                    "Недостаточно свободных мест "
                    "для такого количества человек."
                )

            customer = (
                await self._get_or_create_customer(
                    telegram_id=telegram_id,
                    telegram_username=(
                        telegram_username
                    ),
                    full_name=full_name,
                    phone=phone,
                    source=source,
                )
            )

            person_price = Decimal(
                departure.price
            )

            total_price = (
                person_price
                * people_count
            )

            booking = Booking(
                customer_id=customer.id,
                departure_id=departure.id,
                status="Новая",
                people_count=people_count,
                applicant_full_name=full_name,
                applicant_phone=phone,
                applicant_telegram_username=(
                    telegram_username.strip().lstrip("@")
                    if telegram_username
                    else None
                ),
                applicant_telegram_id=telegram_id,
                agreed_price=total_price,
                calculated_price=total_price,
                manual_price=None,
                price_comment=None,
                comment=comment,
                source=source,
            )

            self.session.add(booking)

            await self.session.flush()

            for index in range(
                people_count
            ):
                if index == 0:
                    participant_name = (
                        full_name
                    )
                else:
                    participant_name = (
                        f"Участник {index + 1}"
                    )

                participant = Participant(
                    booking_id=booking.id,
                    full_name=participant_name,
                    room_id=None,
                    ticket_status="Не куплен",
                    occupied_beds=1,
                    comment=None,
                )

                # Размещение никогда не назначаем автоматически.
                # И Telegram-заявка, и ручная заявка начинают
                # с состояния «Не выбрано».
                participant.accommodation_rate_id = None
                participant.accommodation_type = None
                participant.accommodation_price = None

                self.session.add(
                    participant
                )

            await self.session.commit()

            # Новая Telegram-заявка без оплаты
            # пока не резервирует место.
            remaining_free_places = (
                free_places
            )

            return BookingCreationResult(
                booking=booking,
                departure=departure,
                total_price=total_price,
                free_places=(
                    remaining_free_places
                ),
            )

        except Exception:
            await self.session.rollback()
            raise

    async def _get_locked_departure(
        self,
        departure_id: int,
    ) -> TourDeparture | None:
        result = await self.session.execute(
            select(TourDeparture)
            .options(
                selectinload(
                    TourDeparture.tour
                )
            )
            .where(
                TourDeparture.id
                == departure_id
            )
            .with_for_update()
        )

        return result.scalar_one_or_none()

    async def _get_occupied_places(
        self,
        departure_id: int,
    ) -> int:
        successful_paid = (
            select(
                func.coalesce(
                    func.sum(Payment.amount),
                    0,
                )
            )
            .where(
                Payment.booking_id == Booking.id,
                Payment.status.in_(["paid", "succeeded"]),
                Payment.amount > 0,
            )
            .correlate(Booking)
            .scalar_subquery()
        )

        successful_refunded = (
            select(
                func.coalesce(
                    func.sum(PaymentRefund.amount),
                    0,
                )
            )
            .join(
                Payment,
                Payment.id == PaymentRefund.payment_id,
            )
            .where(
                Payment.booking_id == Booking.id,
                Payment.status.in_(["paid", "succeeded"]),
                PaymentRefund.status == "succeeded",
                PaymentRefund.amount > 0,
            )
            .correlate(Booking)
            .scalar_subquery()
        )

        result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(Booking.people_count),
                    0,
                )
            )
            .where(
                Booking.departure_id == departure_id,
                Booking.status.notin_(["Отмена", "Не актуальна"]),
                successful_paid - successful_refunded > 0,
            )
        )

        return int(result.scalar_one())


    async def _get_or_create_customer(
        self,
        *,
        telegram_id: int,
        telegram_username: str | None,
        full_name: str,
        phone: str,
        source: str,
    ) -> Customer:
        result = await self.session.execute(
            select(Customer)
            .where(
                Customer.telegram_id
                == telegram_id
            )
        )

        customer = (
            result.scalar_one_or_none()
        )

        clean_username = (
            telegram_username.strip()
            .lstrip("@")
            if telegram_username
            else None
        )

        if customer is not None:
            # Один Telegram-аккаунт может отправлять заявки
            # за разных людей (например, за друга). Поэтому
            # данные конкретного заявителя хранятся в Booking
            # snapshot-полях и не должны перезаписывать
            # карточку Customer при каждой новой заявке.
            #
            # Telegram username относится к самому аккаунту,
            # поэтому его можно безопасно актуализировать.
            customer.telegram_username = clean_username

            await self.session.flush()

            return customer

        customer = Customer(
            telegram_id=telegram_id,
            telegram_username=(
                clean_username
            ),
            full_name=full_name,
            phone=phone,
            source=source,
        )

        self.session.add(customer)

        await self.session.flush()

        return customer