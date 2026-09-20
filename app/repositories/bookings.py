from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import Booking, Customer, Payment


class BookingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_customer(
        self,
        telegram_id: int | None,
        telegram_username: str | None,
        full_name: str,
        phone: str | None,
        source: str = "telegram",
    ) -> Customer:
        customer = None

        if telegram_id is not None:
            result = await self.session.execute(
                select(Customer).where(
                    Customer.telegram_id == telegram_id
                )
            )
            customer = result.scalar_one_or_none()

        if customer is None:
            customer = Customer(
                telegram_id=telegram_id,
                telegram_username=telegram_username,
                full_name=full_name,
                phone=phone,
                source=source,
            )
            self.session.add(customer)
            await self.session.flush()

            return customer

        customer.telegram_username = telegram_username
        customer.full_name = full_name
        customer.phone = phone

        await self.session.flush()

        return customer

    async def create_booking(
        self,
        customer_id: int,
        departure_id: int,
        people_count: int,
        price_per_person: Decimal,
        comment: str | None = None,
        source: str = "telegram",
    ) -> Booking:
        total_price = price_per_person * people_count

        booking = Booking(
            customer_id=customer_id,
            departure_id=departure_id,
            status="Новая",
            people_count=people_count,
            agreed_price=total_price,
            comment=comment,
            source=source,
        )

        self.session.add(booking)
        await self.session.flush()

        return booking

    async def get_booking(self, booking_id: int) -> Booking | None:
        result = await self.session.execute(
            select(Booking)
            .options(
                selectinload(Booking.customer),
                selectinload(Booking.departure),
                selectinload(Booking.payments),
            )
            .where(Booking.id == booking_id)
        )

        return result.scalar_one_or_none()

    async def get_paid_amount(
        self,
        booking_id: int,
    ) -> Decimal:
        result = await self.session.execute(
            select(
                func.coalesce(
                    func.sum(Payment.amount),
                    Decimal("0"),
                )
            ).where(
                Payment.booking_id == booking_id,
                Payment.status.in_(["paid", "succeeded"]),
            )
        )

        return Decimal(result.scalar_one())

    async def get_remaining_amount(
        self,
        booking: Booking,
    ) -> Decimal:
        paid = await self.get_paid_amount(booking.id)

        remaining = booking.agreed_price - paid

        return max(remaining, Decimal("0"))

    async def commit(self) -> None:
        await self.session.commit()