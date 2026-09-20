from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.models import (
    Booking,
    Expense,
    Payment,
    TourDeparture,
    TourType,
)
from app.database.session import SessionLocal
from app.crm.seasons import available_seasons, current_season_label, departure_season


router = APIRouter()

CLOSED_BOOKING_STATUSES = {
    "Отмена",
    "Не актуальна",
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
    return f"{int(value):,}".replace(",", " ")


def parse_money(value: str) -> Decimal:
    return Decimal(
        value.strip()
        .replace(" ", "")
        .replace(",", ".")
    )


def payment_refunded_total(payment) -> Decimal:
    return sum(
        (
            Decimal(refund.amount)
            for refund in payment.refunds
            if (
                refund.status in SUCCESS_REFUND_STATUSES
                and Decimal(refund.amount) > 0
            )
        ),
        Decimal("0"),
    )


def booking_gross_paid_total(booking: Booking) -> Decimal:
    return sum(
        (
            Decimal(payment.amount)
            for payment in booking.payments
            if (
                payment.status in SUCCESS_PAYMENT_STATUSES
                and Decimal(payment.amount) > 0
            )
        ),
        Decimal("0"),
    )


def booking_refunded_total(booking: Booking) -> Decimal:
    return sum(
        (payment_refunded_total(payment) for payment in booking.payments),
        Decimal("0"),
    )


def booking_paid_total(booking: Booking) -> Decimal:
    return max(
        booking_gross_paid_total(booking)
        - booking_refunded_total(booking),
        Decimal("0"),
    )


def booking_is_planned(booking: Booking) -> bool:
    return booking.status not in CLOSED_BOOKING_STATUSES


def booking_is_actual_sale(booking: Booking) -> bool:
    return (
        booking_is_planned(booking)
        and booking_paid_total(booking) > 0
    )


async def load_departure(session, departure_id: int):
    result = await session.execute(
        select(TourDeparture)
        .options(
            selectinload(TourDeparture.tour)
            .selectinload(TourType.category),
            selectinload(TourDeparture.bookings)
            .selectinload(Booking.payments)
            .selectinload(Payment.refunds),
            selectinload(TourDeparture.expenses),
        )
        .where(TourDeparture.id == departure_id)
    )

    return (
        result.scalars()
        .unique()
        .one_or_none()
    )


def departure_finance(departure: TourDeparture) -> dict:
    planned_bookings = [
        booking
        for booking in departure.bookings
        if booking_is_planned(booking)
    ]

    actual_bookings = [
        booking
        for booking in planned_bookings
        if booking_is_actual_sale(booking)
    ]

    planned_sales = sum(
        (Decimal(booking.agreed_price or 0) for booking in planned_bookings),
        Decimal("0"),
    )
    actual_sales = sum(
        (Decimal(booking.agreed_price or 0) for booking in actual_bookings),
        Decimal("0"),
    )

    # Денежный поток считаем по всем заявкам, включая отменённые:
    # деньги могли реально поступить и затем быть возвращены.
    gross_received = sum(
        (booking_gross_paid_total(booking) for booking in departure.bookings),
        Decimal("0"),
    )
    refunded = sum(
        (booking_refunded_total(booking) for booking in departure.bookings),
        Decimal("0"),
    )
    net_received = max(gross_received - refunded, Decimal("0"))

    active_net_paid = sum(
        (booking_paid_total(booking) for booking in actual_bookings),
        Decimal("0"),
    )
    remaining = max(actual_sales - active_net_paid, Decimal("0"))

    expenses_total = sum(
        (Decimal(expense.amount or 0) for expense in departure.expenses),
        Decimal("0"),
    )

    planned_profit = planned_sales - expenses_total
    actual_profit = actual_sales - expenses_total
    cash_result = net_received - expenses_total

    people_count = sum(booking.people_count for booking in actual_bookings)
    profit_per_person = (
        actual_profit / people_count if people_count > 0 else Decimal("0")
    )

    return {
        "planned_sales": planned_sales,
        "actual_sales": actual_sales,
        "gross_received": gross_received,
        "refunded": refunded,
        "net_received": net_received,
        "paid": net_received,
        "remaining": remaining,
        "expenses_total": expenses_total,
        "planned_profit": planned_profit,
        "actual_profit": actual_profit,
        "cash_result": cash_result,
        "people_count": people_count,
        "profit_per_person": profit_per_person,
    }


@router.get("/finance", response_class=HTMLResponse)
async def finance_overview(
    request: Request,
    view: str = "active",
    season: str = "",
):
    today = date.today()

    allowed_views = {
        "active",
        "upcoming",
        "past",
        "archive",
        "all",
    }
    if view not in allowed_views:
        view = "active"

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourDeparture)
            .options(
                selectinload(TourDeparture.tour)
            .selectinload(TourType.category),
                selectinload(TourDeparture.bookings)
                .selectinload(Booking.payments)
                .selectinload(Payment.refunds),
                selectinload(TourDeparture.expenses),
            )
        )

        departures = list(
            result.scalars()
            .unique()
            .all()
        )

    seasons = available_seasons(departures)
    selected_season = season.strip()
    if not selected_season:
        current = current_season_label(today)
        selected_season = current if current in seasons else (seasons[0] if seasons else "")
    elif selected_season not in seasons:
        selected_season = seasons[0] if seasons else ""

    season_departures = [
        departure
        for departure in departures
        if not selected_season or departure_season(departure) == selected_season
    ]

    def is_archived(departure: TourDeparture) -> bool:
        return bool(getattr(departure, "archived", False))

    def status_key(departure: TourDeparture) -> str:
        if is_archived(departure):
            return "archive"
        if departure.start_date <= today <= departure.end_date:
            return "current"
        if departure.start_date > today:
            return "upcoming"
        return "past"

    def visible_in_view(departure: TourDeparture) -> bool:
        status = status_key(departure)
        if view == "active":
            return status in {"current", "upcoming"}
        if view == "upcoming":
            return status == "upcoming"
        if view == "past":
            return status == "past"
        if view == "archive":
            return status == "archive"
        return True

    counts = {
        "active": 0,
        "upcoming": 0,
        "past": 0,
        "archive": 0,
        "all": len(season_departures),
    }

    for departure in season_departures:
        status = status_key(departure)
        if status in {"current", "upcoming"}:
            counts["active"] += 1
        if status == "upcoming":
            counts["upcoming"] += 1
        elif status == "past":
            counts["past"] += 1
        elif status == "archive":
            counts["archive"] += 1

    filtered_departures = [
        departure
        for departure in season_departures
        if visible_in_view(departure)
    ]

    def departure_sort_key(departure: TourDeparture):
        status = status_key(departure)
        rank = {
            "current": 0,
            "upcoming": 1,
            "past": 2,
            "archive": 3,
        }[status]

        if status in {"current", "upcoming"}:
            date_key = departure.start_date.toordinal()
        else:
            date_key = -departure.start_date.toordinal()

        return (
            (departure.tour.title or "").casefold(),
            rank,
            date_key,
            departure.id,
        )

    filtered_departures.sort(key=departure_sort_key)

    groups_by_tour = {}
    group_order = []

    totals = {
        "planned_sales": Decimal("0"),
        "actual_sales": Decimal("0"),
        "gross_received": Decimal("0"),
        "refunded": Decimal("0"),
        "net_received": Decimal("0"),
        "paid": Decimal("0"),
        "remaining": Decimal("0"),
        "expenses_total": Decimal("0"),
        "planned_profit": Decimal("0"),
        "actual_profit": Decimal("0"),
        "people_count": 0,
    }

    for departure in filtered_departures:
        finance = departure_finance(departure)
        status = status_key(departure)
        row = {
            "departure": departure,
            "status": status,
            **finance,
        }

        tour_id = departure.tour_id
        if tour_id not in groups_by_tour:
            groups_by_tour[tour_id] = {
                "tour": departure.tour,
                "rows": [],
            }
            group_order.append(tour_id)

        groups_by_tour[tour_id]["rows"].append(row)

        for key in (
            "planned_sales",
            "actual_sales",
            "gross_received",
            "refunded",
            "net_received",
            "paid",
            "remaining",
            "expenses_total",
            "planned_profit",
            "actual_profit",
        ):
            totals[key] += finance[key]

        totals["people_count"] += finance["people_count"]

    groups = [groups_by_tour[tour_id] for tour_id in group_order]

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="finance_overview.html",
        context={
            "groups": groups,
            "totals": totals,
            "today": today,
            "view": view,
            "counts": counts,
            "seasons": seasons,
            "selected_season": selected_season,
            "format_money": format_money,
        },
    )


@router.get(
    "/departures/{departure_id}/finance",
    response_class=HTMLResponse,
)
async def finance_page(
    request: Request,
    departure_id: int,
):
    async with SessionLocal() as session:
        departure = await load_departure(
            session,
            departure_id,
        )

        if departure is None:
            return HTMLResponse(
                "Поездка не найдена",
                status_code=404,
            )

        finance = departure_finance(departure)

        expenses = sorted(
            departure.expenses,
            key=lambda expense: (
                expense.expense_date or date.min,
                expense.id,
            ),
            reverse=True,
        )

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="finance.html",
        context={
            "departure": departure,
            **finance,
            "expenses": expenses,
            "format_money": format_money,
        },
    )


@router.post(
    "/departures/{departure_id}/expenses/add"
)
async def add_expense(
    departure_id: int,
    category: str = Form(...),
    amount: str = Form(...),
    expense_date: str = Form(""),
    description: str = Form(""),
):
    category = category.strip()
    description = description.strip()

    if not category:
        return HTMLResponse(
            "Укажите категорию расхода",
            status_code=400,
        )

    try:
        expense_amount = parse_money(amount)
    except InvalidOperation:
        return HTMLResponse(
            "Некорректная сумма расхода",
            status_code=400,
        )

    if expense_amount <= 0:
        return HTMLResponse(
            "Сумма расхода должна быть больше 0",
            status_code=400,
        )

    parsed_date = None

    if expense_date.strip():
        try:
            parsed_date = date.fromisoformat(
                expense_date.strip()
            )
        except ValueError:
            return HTMLResponse(
                "Некорректная дата расхода",
                status_code=400,
            )

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourDeparture)
            .where(TourDeparture.id == departure_id)
        )

        departure = result.scalar_one_or_none()

        if departure is None:
            return HTMLResponse(
                "Поездка не найдена",
                status_code=404,
            )

        session.add(
            Expense(
                departure_id=departure_id,
                category=category,
                description=description or None,
                amount=expense_amount,
                expense_date=parsed_date,
            )
        )

        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}/finance",
        status_code=303,
    )


@router.post(
    "/expenses/{expense_id}/delete"
)
async def delete_expense(expense_id: int):
    async with SessionLocal() as session:
        result = await session.execute(
            select(Expense)
            .where(Expense.id == expense_id)
        )

        expense = result.scalar_one_or_none()

        if expense is None:
            return HTMLResponse(
                "Расход не найден",
                status_code=404,
            )

        departure_id = expense.departure_id

        await session.delete(expense)
        await session.commit()

    return RedirectResponse(
        url=f"/departures/{departure_id}/finance",
        status_code=303,
    )
