from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)


class Base(DeclarativeBase):
    pass


class TourCategory(Base):
    __tablename__ = "tour_categories"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255)
    )

    emoji: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    tours: Mapped[list["TourType"]] = relationship(
        back_populates="category",
    )

    media: Mapped[list["TourMedia"]] = relationship(
        back_populates="category",
        passive_deletes=True,
    )


class TourType(Base):
    __tablename__ = "tour_types"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    category_id: Mapped[int] = mapped_column(
        ForeignKey("tour_categories.id"),
        index=True,
    )

    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(
        String(255)
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    accommodation_description: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    transport: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    includes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    not_included: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    program: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    category: Mapped["TourCategory"] = relationship(
        back_populates="tours",
    )

    departures: Mapped[list["TourDeparture"]] = relationship(
        back_populates="tour",
        cascade="all, delete-orphan",
    )
    media: Mapped[list["TourMedia"]] = relationship(
        back_populates="tour",
        cascade="all, delete-orphan",
    )


class TourMedia(Base):
    __tablename__ = "tour_media"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    category_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "tour_categories.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    tour_id: Mapped[int | None] = mapped_column(
        ForeignKey("tour_types.id"),
        nullable=True,
        index=True,
    )

    section: Mapped[str] = mapped_column(
        String(50),
        index=True,
    )

    media_type: Mapped[str] = mapped_column(
        String(20),
        default="photo",
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    telegram_file_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    sort_order: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    category: Mapped["TourCategory | None"] = relationship(
        back_populates="media",
    )

    tour: Mapped["TourType | None"] = relationship(
        back_populates="media",
    )


class TourDeparture(Base):
    __tablename__ = "tour_departures"

    id: Mapped[int] = mapped_column(primary_key=True)

    tour_id: Mapped[int] = mapped_column(
        ForeignKey("tour_types.id"),
        index=True,
    )

    start_date: Mapped[date] = mapped_column(Date)

    end_date: Mapped[date] = mapped_column(Date)

    season: Mapped[str] = mapped_column(
        String(20),
        index=True,
    )

    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
    )

    prepayment_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0"),
    )

    capacity: Mapped[int] = mapped_column(
        Integer,
        default=20,
    )

    booking_open: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        index=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    tour: Mapped["TourType"] = relationship(
        back_populates="departures",
    )

    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="departure",
    )

    expenses: Mapped[list["Expense"]] = relationship(
        back_populates="departure",
        cascade="all, delete-orphan",
    )

    rooms: Mapped[list["Room"]] = relationship(
        back_populates="departure",
        cascade="all, delete-orphan",
    )

    accommodation_rates: Mapped[
        list["AccommodationRate"]
    ] = relationship(
        back_populates="departure",
        cascade="all, delete-orphan",
    )


class AccommodationRate(Base):
    __tablename__ = "accommodation_rates"

    __table_args__ = (
        UniqueConstraint(
            "departure_id",
            "code",
            name="uq_accommodation_rate_departure_code",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    departure_id: Mapped[int] = mapped_column(
        ForeignKey("tour_departures.id"),
        index=True,
    )

    code: Mapped[str] = mapped_column(
        String(50)
    )

    title: Mapped[str] = mapped_column(
        String(100)
    )

    price_per_person: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
    )

    occupied_beds: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    departure: Mapped["TourDeparture"] = relationship(
        back_populates="accommodation_rates",
    )

    participants: Mapped[
        list["Participant"]
    ] = relationship(
        back_populates="accommodation_rate",
    )


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger,
        unique=True,
        nullable=True,
        index=True,
    )

    telegram_username: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(255)
    )

    phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default="telegram",
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="customer",
    )


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        index=True,
    )

    departure_id: Mapped[int] = mapped_column(
        ForeignKey("tour_departures.id"),
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="Новая",
        index=True,
    )

    people_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    applicant_full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    applicant_phone: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    applicant_telegram_username: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        nullable=True,
    )

    applicant_telegram_id: Mapped[
        int | None
    ] = mapped_column(
        BigInteger,
        nullable=True,
        index=True,
    )

    agreed_price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
    )

    calculated_price: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    manual_price: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    price_comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default="telegram",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    customer: Mapped["Customer"] = relationship(
        back_populates="bookings",
    )

    departure: Mapped["TourDeparture"] = relationship(
        back_populates="bookings",
    )

    participants: Mapped[
        list["Participant"]
    ] = relationship(
        back_populates="booking",
        cascade="all, delete-orphan",
    )

    payments: Mapped[list["Payment"]] = relationship(
        back_populates="booking",
        cascade="all, delete-orphan",
    )


class Room(Base):
    __tablename__ = "rooms"

    __table_args__ = (
        UniqueConstraint(
            "departure_id",
            "number",
            name="uq_room_departure_number",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    departure_id: Mapped[int] = mapped_column(
        ForeignKey("tour_departures.id"),
        index=True,
    )

    number: Mapped[str] = mapped_column(
        String(100)
    )

    room_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    capacity: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    departure: Mapped["TourDeparture"] = relationship(
        back_populates="rooms",
    )

    participants: Mapped[
        list["Participant"]
    ] = relationship(
        back_populates="room",
    )


class Participant(Base):
    __tablename__ = "participants"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id"),
        index=True,
    )

    room_id: Mapped[int | None] = mapped_column(
        ForeignKey("rooms.id"),
        nullable=True,
        index=True,
    )

    accommodation_rate_id: Mapped[
        int | None
    ] = mapped_column(
        ForeignKey("accommodation_rates.id"),
        nullable=True,
        index=True,
    )

    full_name: Mapped[str] = mapped_column(
        String(255)
    )

    accommodation_type: Mapped[
        str | None
    ] = mapped_column(
        String(100),
        nullable=True,
    )

    accommodation_price: Mapped[
        Decimal | None
    ] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    occupied_beds: Mapped[int] = mapped_column(
        Integer,
        default=1,
    )

    ticket_status: Mapped[str] = mapped_column(
        String(50),
        default="Не куплен",
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    booking: Mapped["Booking"] = relationship(
        back_populates="participants",
    )

    room: Mapped["Room | None"] = relationship(
        back_populates="participants",
    )

    accommodation_rate: Mapped[
        "AccommodationRate | None"
    ] = relationship(
        back_populates="participants",
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    booking_id: Mapped[int] = mapped_column(
        ForeignKey("bookings.id"),
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="pending",
        index=True,
    )

    payment_type: Mapped[str] = mapped_column(
        String(50),
        default="manual",
    )

    provider: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    provider_payment_id: Mapped[
        str | None
    ] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    paid_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    booking: Mapped["Booking"] = relationship(
        back_populates="payments",
    )

    refunds: Mapped[list["PaymentRefund"]] = relationship(
        back_populates="payment",
        cascade="all, delete-orphan",
    )


class PaymentRefund(Base):
    __tablename__ = "payment_refunds"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    payment_id: Mapped[int] = mapped_column(
        ForeignKey("payments.id"),
        index=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="succeeded",
        index=True,
    )

    refund_method: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    refunded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    payment: Mapped["Payment"] = relationship(
        back_populates="refunds",
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    departure_id: Mapped[int] = mapped_column(
        ForeignKey("tour_departures.id"),
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(100)
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2)
    )

    expense_date: Mapped[
        date | None
    ] = mapped_column(
        Date,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    departure: Mapped["TourDeparture"] = relationship(
        back_populates="expenses",
    )


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(
        primary_key=True
    )

    telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
    )

    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(50),
        default="admin",
    )

    active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )