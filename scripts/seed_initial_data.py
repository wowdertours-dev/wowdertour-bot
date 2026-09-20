import asyncio
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.database.models import TourCategory, TourDeparture, TourType
from app.database.session import SessionLocal
from app.crm.seasons import season_from_date


TOURS = [
    {
        "category_slug": "snowboard",
        "slug": "kirovsk",
        "title": "🏂 Кировск",
        "description": (
            "Сноуборд-тур в Хибины для новичков и опытных райдеров. "
            "Тренировки, фрирайд с сертифицированными гидами "
            "и сопровождение организаторов."
        ),
        "transport": "🚆 Поезд Санкт-Петербург ⇄ Апатиты",
        "includes": (
            "🚆 Поезд Санкт-Петербург ⇄ Апатиты\n"
            "🛏️ Проживание на весь тур\n"
            "🚍 Трансфер вокзал ⇄ проживание\n"
            "🚐 Ежедневный трансфер до склонов и обратно\n"
            "🎿 Тренировки по сноуборду для новичков и опытных райдеров\n"
            "🏔️ Фрирайд с сертифицированными гидами\n"
            "🎉 Вечерние активности и сопровождение организаторов"
        ),
        "not_included": (
            "🎫 Ски-пасс\n"
            "🍔 Питание"
        ),
        "departures": [
            ("2026-12-10", "2026-12-16", 42000, 20),
            ("2027-01-04", "2027-01-10", 42000, 20),
            ("2027-03-04", "2027-03-09", 42000, 20),
            ("2027-04-11", "2027-04-16", 42000, 20),
            ("2027-05-06", "2027-05-11", 42000, 20),
        ],
    },
    {
        "category_slug": "snowboard",
        "slug": "sheregesh",
        "title": "🏔️ Шерегеш",
        "description": (
            "Фрирайд-тур в Шерегеш с тренировками, "
            "катанием и сопровождением команды."
        ),
        "transport": "✈️ Перелёт + трансфер Новокузнецк → Шерегеш",
        "includes": (
            "🏡 Проживание в просторном люкс-коттедже\n"
            "🚐 Трансфер Новокузнецк → Шерегеш\n"
            "🚐 Ежедневный трансфер до горы\n"
            "🏂 Сопровождение и тренировки от Никиты и Гены\n"
            "🎉 Организация досуга внутри тура"
        ),
        "not_included": (
            "✈️ Перелёт\n"
            "🍽️ Питание\n"
            "🎫 Ски-пасс"
        ),
        "departures": [
            ("2026-11-21", "2026-11-28", 68000, 20),
        ],
    },
    {
        "category_slug": "wake",
        "slug": "wake",
        "title": "🏄 Вейк-туры",
        "description": (
            "Летние вейк-туры. Новые даты будут появляться "
            "по мере открытия сезона."
        ),
        "transport": None,
        "includes": None,
        "not_included": None,
        "departures": [],
    },
    {
        "category_slug": "skate",
        "slug": "skate",
        "title": "🛹 Скейт-интенсивы",
        "description": (
            "Однодневные скейт-интенсивы в Санкт-Петербурге "
            "и Ленинградской области."
        ),
        "transport": None,
        "includes": None,
        "not_included": None,
        "departures": [],
    },
]


async def seed() -> None:
    async with SessionLocal() as session:
        for tour_data in TOURS:
            category_result = await session.execute(
                select(TourCategory).where(
                    TourCategory.slug == tour_data["category_slug"]
                )
            )
            category = category_result.scalar_one_or_none()

            if category is None:
                raise RuntimeError(
                    "Категории не найдены. Сначала выполните `alembic upgrade head`."
                )

            result = await session.execute(
                select(TourType).where(
                    TourType.slug == tour_data["slug"]
                )
            )
            tour = result.scalar_one_or_none()

            if tour is None:
                tour = TourType(
                    category_id=category.id,
                    slug=tour_data["slug"],
                    title=tour_data["title"],
                    description=tour_data["description"],
                    transport=tour_data["transport"],
                    includes=tour_data["includes"],
                    not_included=tour_data["not_included"],
                    active=True,
                )
                session.add(tour)
                await session.flush()

                print(f"Создан тур: {tour.title}")
            else:
                print(f"Тур уже существует: {tour.title}")

            for start, end, price, capacity in tour_data["departures"]:
                start_date = date.fromisoformat(start)
                end_date = date.fromisoformat(end)

                result = await session.execute(
                    select(TourDeparture).where(
                        TourDeparture.tour_id == tour.id,
                        TourDeparture.start_date == start_date,
                        TourDeparture.end_date == end_date,
                    )
                )

                departure = result.scalar_one_or_none()

                if departure is not None:
                    print(
                        f"  Дата уже существует: "
                        f"{start_date} — {end_date}"
                    )
                    continue

                session.add(
                    TourDeparture(
                        tour_id=tour.id,
                        start_date=start_date,
                        end_date=end_date,
                        season=season_from_date(start_date),
                        price=Decimal(str(price)),
                        prepayment_amount=Decimal("0"),
                        capacity=capacity,
                        booking_open=True,
                        active=True,
                    )
                )

                print(
                    f"  Добавлена дата: "
                    f"{start_date} — {end_date}"
                )

        await session.commit()

    print("\nБаза WowderTour заполнена.")


if __name__ == "__main__":
    asyncio.run(seed())