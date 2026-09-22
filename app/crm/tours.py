import base64
import binascii
from urllib.parse import urlsplit

from datetime import date
from decimal import (
    Decimal,
    InvalidOperation,
)

from fastapi import (
    APIRouter,
    File,
    Form,
    Request,
    UploadFile,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from sqlalchemy import (
    case,
    func,
    select,
)
from sqlalchemy.orm import defer, selectinload, with_expression

from app.database.models import (
    Booking,
    Payment,
    TourCategory,
    TourDeparture,
    TourMedia,
    TourType,
)
from app.database.session import (
    SessionLocal,
)
from app.crm.seasons import available_seasons, current_season_label, departure_season, normalize_season
from app.repositories.tours import (
    get_occupied_places,
)


router = APIRouter()

MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTO_BATCH_BYTES = 20 * 1024 * 1024
MAX_PHOTO_BATCH_COUNT = 5


def media_preview_option():
    # Return only availability, never the potentially huge base64 payload.
    # This is a read-only projection; stored URLs remain unchanged.
    return with_expression(
        TourMedia.url,
        case(
            (TourMedia.url.is_not(None) & (TourMedia.url != ""), "available"),
            else_=None,
        ),
    )


@router.get("/media/{media_id}/image")
async def media_image(media_id: int):
    # Protected by the same CRM authentication middleware as the gallery.
    async with SessionLocal() as session:
        source = await session.scalar(
            select(TourMedia.url).where(TourMedia.id == media_id)
        )
    if not source:
        return Response(status_code=404)
    if source.startswith("data:"):
        header, separator, encoded = source.partition(",")
        del source
        mime = header[5:].removesuffix(";base64").lower()
        allowed = {"image/jpeg", "image/png", "image/webp", "image/gif",
                   "image/bmp", "image/tiff", "image/avif", "image/heic",
                   "image/heif", "image/x-icon"}
        if (not separator or not header.endswith(";base64") or mime not in allowed
                or len(encoded) > 4 * ((MAX_PHOTO_BYTES + 2) // 3)):
            return Response(status_code=415)
        try:
            content = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            return Response(status_code=415)
        if not content or len(content) > MAX_PHOTO_BYTES:
            return Response(status_code=415)
        return Response(content, media_type=mime,
                        headers={"X-Content-Type-Options": "nosniff"})
    try:
        parsed = urlsplit(source)
    except ValueError:
        return Response(status_code=415)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return RedirectResponse(source)
    return Response(status_code=415)



CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


def make_slug(
    value: str,
) -> str:
    result = []

    for character in value.lower().strip():
        if character in CYRILLIC_TO_LATIN:
            result.append(
                CYRILLIC_TO_LATIN[
                    character
                ]
            )

        elif character.isalnum():
            result.append(
                character
            )

        elif character in {
            " ",
            "_",
            "-",
        }:
            result.append("-")

    slug = "".join(result)

    while "--" in slug:
        slug = slug.replace(
            "--",
            "-",
        )

    return slug.strip("-")


async def unique_category_slug(
    session,
    title: str,
) -> str:
    base_slug = (
        make_slug(title)
        or "category"
    )

    slug = base_slug
    counter = 2

    while True:
        result = await session.execute(
            select(TourCategory.id)
            .where(
                TourCategory.slug
                == slug
            )
        )

        if result.scalar_one_or_none() is None:
            return slug

        slug = (
            f"{base_slug}-"
            f"{counter}"
        )

        counter += 1


async def unique_tour_slug(
    session,
    title: str,
) -> str:
    base_slug = (
        make_slug(title)
        or "tour"
    )

    slug = base_slug
    counter = 2

    while True:
        result = await session.execute(
            select(TourType.id)
            .where(
                TourType.slug
                == slug
            )
        )

        if result.scalar_one_or_none() is None:
            return slug

        slug = (
            f"{base_slug}-"
            f"{counter}"
        )

        counter += 1


def parse_money(
    value: str,
) -> Decimal:
    cleaned = (
        value.strip()
        .replace(" ", "")
        .replace(",", ".")
    )

    return Decimal(cleaned)


def checkbox_value(
    value: str | None,
) -> bool:
    return value == "1"


def departure_people_count(
    departure: TourDeparture,
) -> int:
    """
    Количество занятых мест в CRM.

    Место считается занятым только если у заявки
    есть успешная фактическая оплата/предоплата.
    Заявки «Отмена» и «Не актуальна» места не занимают.
    """
    return get_occupied_places(departure)


async def upload_to_data_url(
    upload: UploadFile,
) -> str:
    if not upload.content_type:
        raise ValueError(
            "Не удалось определить тип файла"
        )

    if not upload.content_type.startswith(
        "image/"
    ):
        raise ValueError(
            "Можно загружать только изображения"
        )

    if upload.size is not None and upload.size > MAX_PHOTO_BYTES:
        raise ValueError("Фото должно быть не больше 10 МБ")
    content = await upload.read(MAX_PHOTO_BYTES + 1)

    if not content:
        raise ValueError(
            "Файл пустой"
        )

    max_size = MAX_PHOTO_BYTES

    if len(content) > max_size:
        raise ValueError(
            "Фото должно быть не больше 10 МБ"
        )

    encoded = base64.b64encode(
        content
    ).decode("ascii")

    return (
        f"data:{upload.content_type};"
        f"base64,{encoded}"
    )


async def get_categories(
    session,
) -> list[TourCategory]:
    result = await session.execute(
        select(TourCategory)
        .options(
            selectinload(
                TourCategory.media
            ).options(media_preview_option()),
            selectinload(
                TourCategory.tours
            )
            .selectinload(
                TourType.media
            ).options(media_preview_option()),
            selectinload(
                TourCategory.tours
            )
            .selectinload(
                TourType.departures
            )
            .selectinload(
                TourDeparture.bookings
            )
            .selectinload(
                Booking.payments
            )
            .selectinload(
                Payment.refunds
            ),
        )
        .order_by(
            TourCategory.sort_order,
            TourCategory.title,
        )
    )

    categories = list(
        result.scalars()
        .unique()
        .all()
    )

    for category in categories:
        category.media.sort(
            key=lambda media: (
                media.sort_order,
                media.id,
            )
        )

        category.tours.sort(
            key=lambda tour:
                tour.title
        )

        for tour in category.tours:
            tour.media.sort(
                key=lambda media: (
                    media.sort_order,
                    media.id,
                )
            )

            tour.departures.sort(
                key=lambda departure:
                    departure.start_date
            )

    return categories


@router.get(
    "/tours/manage",
    response_class=HTMLResponse,
)
async def tours_management_page(
    request: Request,
):
    async with SessionLocal() as session:
        categories = await get_categories(
            session
        )

        about_media_result = (
            await session.execute(
                select(TourMedia).options(media_preview_option())
                .where(
                    TourMedia.category_id
                    .is_(None),
                    TourMedia.tour_id
                    .is_(None),
                    TourMedia.section
                    == "about",
                )
                .order_by(
                    TourMedia.sort_order,
                    TourMedia.id,
                )
            )
        )

        about_media = list(
            about_media_result
            .scalars()
            .all()
        )

        return (
            request.app.state.templates
            .TemplateResponse(
                request=request,
                name="tours.html",
                context={
                    "categories":
                        categories,
                    "departure_people_count":
                        departure_people_count,
                    "today":
                        date.today(),
                    "about_media":
                        about_media,
                },
            )
        )


@router.get(
    "/tours/{tour_id}/manage",
    response_class=HTMLResponse,
)
async def tour_direction_page(
    request: Request,
    tour_id: int,
    view: str = "active",
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourType)
            .options(
                selectinload(
                    TourType.category
                ),
                selectinload(
                    TourType.media
                ).options(media_preview_option()),
                selectinload(
                    TourType.departures
                )
                .selectinload(
                    TourDeparture.bookings
                )
                .selectinload(
                    Booking.payments
                )
                .selectinload(
                    Payment.refunds
                ),
            )
            .where(
                TourType.id == tour_id
            )
        )

        tour = (
            result.scalars()
            .unique()
            .one_or_none()
        )

        if tour is None:
            return HTMLResponse(
                "Направление не найдено",
                status_code=404,
            )

        categories_result = (
            await session.execute(
                select(TourCategory)
                .order_by(
                    TourCategory.sort_order,
                    TourCategory.title,
                )
            )
        )

        categories = list(
            categories_result.scalars().all()
        )

        tour.media.sort(
            key=lambda media: (
                media.sort_order,
                media.id,
            )
        )

        tour.departures.sort(
            key=lambda departure:
                departure.start_date
        )

        today = date.today()

        past_changed = False
        for departure in tour.departures:
            if (
                departure.end_date < today
                and departure.booking_open
            ):
                departure.booking_open = False
                past_changed = True

        if past_changed:
            await session.commit()

        allowed_views = {
            "active",
            "all",
            "past",
            "archive",
        }

        if view not in allowed_views:
            view = "active"

        non_archived = [
            departure
            for departure in tour.departures
            if not departure.archived
        ]

        active_departures = [
            departure
            for departure in non_archived
            if departure.end_date >= today
        ]

        past_departures = [
            departure
            for departure in non_archived
            if departure.end_date < today
        ]

        archived_departures = [
            departure
            for departure in tour.departures
            if departure.archived
        ]

        if view == "all":
            visible_departures = non_archived
        elif view == "past":
            visible_departures = past_departures
        elif view == "archive":
            visible_departures = archived_departures
        else:
            visible_departures = active_departures

        if view == "active":
            visible_departures.sort(
                key=lambda departure: (
                    0
                    if (
                        departure.start_date
                        <= today
                        <= departure.end_date
                    )
                    else 1,
                    departure.start_date,
                )
            )
        elif view == "past":
            visible_departures.sort(
                key=lambda departure:
                    departure.end_date,
                reverse=True,
            )
        elif view == "archive":
            visible_departures.sort(
                key=lambda departure:
                    departure.start_date,
                reverse=True,
            )

        return (
            request.app.state.templates
            .TemplateResponse(
                request=request,
                name="tour_direction.html",
                context={
                    "tour": tour,
                    "categories": categories,
                    "departure_people_count":
                        departure_people_count,
                    "today": today,
                    "view": view,
                    "visible_departures":
                        visible_departures,
                    "active_count":
                        len(active_departures),
                    "past_count":
                        len(past_departures),
                    "archive_count":
                        len(archived_departures),
                    "all_count":
                        len(non_archived),
                },
            )
        )


# =========================
# КАТЕГОРИИ
# =========================


@router.post(
    "/tour-categories/add"
)
async def add_category(
    title: str = Form(...),
    emoji: str = Form(""),
):
    title = title.strip()
    emoji = emoji.strip()

    if not title:
        return HTMLResponse(
            "Название категории обязательно",
            status_code=400,
        )

    async with SessionLocal() as session:
        slug = await unique_category_slug(
            session,
            title,
        )

        max_order_result = (
            await session.execute(
                select(
                    func.max(
                        TourCategory.sort_order
                    )
                )
            )
        )

        max_order = (
            max_order_result.scalar_one()
            or 0
        )

        category = TourCategory(
            title=title,
            slug=slug,
            emoji=emoji or None,
            sort_order=max_order + 10,
            active=True,
        )

        session.add(category)

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )



@router.post(
    "/tour-categories/{category_id}/move"
)
async def move_category(
    category_id: int,
    direction: str = Form(...),
):
    if direction not in {"up", "down"}:
        return HTMLResponse(
            "Некорректное направление сортировки",
            status_code=400,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourCategory)
            .order_by(
                TourCategory.sort_order,
                TourCategory.title,
                TourCategory.id,
            )
        )

        categories = list(
            result.scalars().all()
        )

        for index, category in enumerate(
            categories,
            start=1,
        ):
            category.sort_order = index * 10

        current_index = next(
            (
                index
                for index, category
                in enumerate(categories)
                if category.id == category_id
            ),
            None,
        )

        if current_index is None:
            return HTMLResponse(
                "Категория не найдена",
                status_code=404,
            )

        target_index = (
            current_index - 1
            if direction == "up"
            else current_index + 1
        )

        if 0 <= target_index < len(categories):
            current = categories[current_index]
            target = categories[target_index]

            current.sort_order, target.sort_order = (
                target.sort_order,
                current.sort_order,
            )

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )


@router.post(
    "/tour-categories/{category_id}/update"
)
async def update_category(
    category_id: int,
    title: str = Form(...),
    emoji: str = Form(""),
    active: str | None = Form(None),
):
    title = title.strip()
    emoji = emoji.strip()

    if not title:
        return HTMLResponse(
            "Название категории обязательно",
            status_code=400,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourCategory)
            .where(
                TourCategory.id
                == category_id
            )
        )

        category = (
            result.scalar_one_or_none()
        )

        if category is None:
            return HTMLResponse(
                "Категория не найдена",
                status_code=404,
            )

        category.title = title
        category.emoji = (
            emoji or None
        )
        category.active = (
            checkbox_value(active)
        )

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )


# =========================
# НАПРАВЛЕНИЯ
# =========================


@router.post(
    "/tours/add"
)
async def add_tour(
    category_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    accommodation_description: str = Form(""),
    includes: str = Form(""),
    program: str = Form(""),
):
    title = title.strip()

    if not title:
        return HTMLResponse(
            "Название направления обязательно",
            status_code=400,
        )

    async with SessionLocal() as session:
        category_result = (
            await session.execute(
                select(TourCategory)
                .where(
                    TourCategory.id
                    == category_id
                )
            )
        )

        category = (
            category_result
            .scalar_one_or_none()
        )

        if category is None:
            return HTMLResponse(
                "Категория не найдена",
                status_code=404,
            )

        slug = await unique_tour_slug(
            session,
            title,
        )

        tour = TourType(
            category_id=category.id,
            title=title,
            slug=slug,
            description=(
                description.strip()
                or None
            ),
            accommodation_description=(
                accommodation_description.strip()
                or None
            ),
            includes=(
                includes.strip()
                or None
            ),
            program=(
                program.strip()
                or None
            ),
            active=True,
        )

        session.add(tour)

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )


@router.post(
    "/tours/{tour_id}/update"
)
async def update_tour(
    tour_id: int,
    category_id: int = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    accommodation_description: str = Form(""),
    includes: str = Form(""),
    program: str = Form(""),
    active: str | None = Form(None),
    return_to: str = Form("/tours/manage"),
):
    title = title.strip()

    if not title:
        return HTMLResponse(
            "Название направления обязательно",
            status_code=400,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourType)
            .where(
                TourType.id == tour_id
            )
        )

        tour = (
            result.scalar_one_or_none()
        )

        if tour is None:
            return HTMLResponse(
                "Направление не найдено",
                status_code=404,
            )

        category_result = (
            await session.execute(
                select(TourCategory)
                .where(
                    TourCategory.id
                    == category_id
                )
            )
        )

        category = (
            category_result
            .scalar_one_or_none()
        )

        if category is None:
            return HTMLResponse(
                "Категория не найдена",
                status_code=404,
            )

        tour.category_id = (
            category.id
        )

        tour.title = title

        tour.description = (
            description.strip()
            or None
        )

        tour.accommodation_description = (
            accommodation_description.strip()
            or None
        )

        tour.includes = (
            includes.strip()
            or None
        )

        tour.program = (
            program.strip()
            or None
        )

        tour.active = (
            checkbox_value(active)
        )

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )


@router.post(
    "/tours/{tour_id}/delete"
)
async def delete_tour(
    tour_id: int,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourType)
            .options(
                selectinload(
                    TourType.departures
                )
                .selectinload(
                    TourDeparture.bookings
                )
            )
            .where(
                TourType.id == tour_id
            )
        )

        tour = (
            result.scalars()
            .unique()
            .one_or_none()
        )

        if tour is None:
            return HTMLResponse(
                "Направление не найдено",
                status_code=404,
            )

        has_bookings = any(
            departure.bookings
            for departure
            in tour.departures
        )

        if has_bookings:
            return HTMLResponse(
                (
                    "Направление нельзя удалить, "
                    "потому что в нём уже есть заявки. "
                    "Скройте направление вместо удаления."
                ),
                status_code=400,
            )

        await session.delete(
            tour
        )

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )


# =========================
# ПОЕЗДКИ
# =========================


@router.post(
    "/tours/{tour_id}/departures/add"
)
async def add_departure(
    tour_id: int,
    start_date: str = Form(...),
    end_date: str = Form(...),
    price: str = Form(...),
    capacity: int = Form(...),
    prepayment_amount: str = Form("0"),
    season: str = Form(""),
    notes: str = Form(""),
    return_to: str = Form("/tours/manage"),
):
    try:
        start = date.fromisoformat(
            start_date
        )

        end = date.fromisoformat(
            end_date
        )

    except ValueError:
        return HTMLResponse(
            "Некорректная дата",
            status_code=400,
        )

    if end < start:
        return HTMLResponse(
            (
                "Дата окончания не может "
                "быть раньше даты начала"
            ),
            status_code=400,
        )

    # WOWDER_STORED_SEASON_ADD
    try:
        departure_season_value = normalize_season(
            season,
            fallback_date=start,
        )
    except ValueError as error:
        return HTMLResponse(str(error), status_code=400)

    if capacity < 1:
        return HTMLResponse(
            (
                "Вместимость должна быть "
                "больше нуля"
            ),
            status_code=400,
        )

    try:
        departure_price = (
            parse_money(price)
        )

        prepayment = (
            parse_money(
                prepayment_amount
                or "0"
            )
        )

    except InvalidOperation:
        return HTMLResponse(
            "Некорректная сумма",
            status_code=400,
        )

    if departure_price < 0:
        return HTMLResponse(
            "Цена не может быть отрицательной",
            status_code=400,
        )

    if prepayment < 0:
        return HTMLResponse(
            (
                "Предоплата не может быть "
                "отрицательной"
            ),
            status_code=400,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourType)
            .where(
                TourType.id == tour_id
            )
        )

        tour = (
            result.scalar_one_or_none()
        )

        if tour is None:
            return HTMLResponse(
                "Направление не найдено",
                status_code=404,
            )

        departure = TourDeparture(
            tour_id=tour.id,
            start_date=start,
            end_date=end,
            season=departure_season_value,
            price=departure_price,
            prepayment_amount=prepayment,
            capacity=capacity,
            booking_open=True,
            active=True,
            notes=(
                notes.strip()
                or None
            ),
        )

        session.add(departure)

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )


@router.post(
    "/departures/{departure_id}/settings"
)
async def update_departure(
    departure_id: int,
    start_date: str = Form(...),
    end_date: str = Form(...),
    price: str = Form(...),
    capacity: int = Form(...),
    prepayment_amount: str = Form("0"),
    season: str = Form(""),
    notes: str = Form(""),
    booking_open: str | None = Form(
        None
    ),
    active: str | None = Form(None),
    return_to: str = Form("/tours/manage"),
):
    try:
        start = date.fromisoformat(
            start_date
        )

        end = date.fromisoformat(
            end_date
        )

    except ValueError:
        return HTMLResponse(
            "Некорректная дата",
            status_code=400,
        )

    if end < start:
        return HTMLResponse(
            (
                "Дата окончания не может "
                "быть раньше даты начала"
            ),
            status_code=400,
        )

    # WOWDER_STORED_SEASON_UPDATE
    try:
        departure_season_value = normalize_season(
            season,
            fallback_date=start,
        )
    except ValueError as error:
        return HTMLResponse(str(error), status_code=400)

    if capacity < 1:
        return HTMLResponse(
            (
                "Вместимость должна быть "
                "больше нуля"
            ),
            status_code=400,
        )

    try:
        departure_price = (
            parse_money(price)
        )

        prepayment = (
            parse_money(
                prepayment_amount
                or "0"
            )
        )

    except InvalidOperation:
        return HTMLResponse(
            "Некорректная сумма",
            status_code=400,
        )

    if departure_price < 0:
        return HTMLResponse(
            "Цена не может быть отрицательной",
            status_code=400,
        )

    if prepayment < 0:
        return HTMLResponse(
            "Предоплата не может быть отрицательной",
            status_code=400,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourDeparture)
            .options(
                selectinload(
                    TourDeparture.bookings
                )
                .selectinload(
                    Booking.payments
                )
                .selectinload(
                    Payment.refunds
                )
            )
            .where(
                TourDeparture.id
                == departure_id
            )
        )

        departure = (
            result.scalar_one_or_none()
        )

        if departure is None:
            return HTMLResponse(
                "Поездка не найдена",
                status_code=404,
            )

        occupied = (
            departure_people_count(
                departure
            )
        )

        if capacity < occupied:
            return HTMLResponse(
                (
                    "Нельзя поставить "
                    f"вместимость {capacity}. "
                    f"Уже записано: {occupied}."
                ),
                status_code=400,
            )

        departure.start_date = start
        departure.end_date = end
        departure.season = departure_season_value
        departure.price = (
            departure_price
        )
        departure.prepayment_amount = (
            prepayment
        )
        departure.capacity = capacity

        departure.booking_open = (
            checkbox_value(
                booking_open
            )
        )

        departure.active = (
            checkbox_value(active)
        )

        departure.notes = (
            notes.strip()
            or None
        )

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )


@router.post(
    "/departures/{departure_id}/delete"
)
async def delete_departure(
    departure_id: int,
    return_to: str = Form("/tours/manage"),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourDeparture)
            .options(
                selectinload(
                    TourDeparture.bookings
                )
            )
            .where(
                TourDeparture.id
                == departure_id
            )
        )

        departure = (
            result.scalar_one_or_none()
        )

        if departure is None:
            return HTMLResponse(
                "Поездка не найдена",
                status_code=404,
            )

        if departure.bookings:
            return HTMLResponse(
                (
                    "Поездку нельзя удалить, "
                    "потому что по ней уже есть заявки. "
                    "Скройте поездку вместо удаления."
                ),
                status_code=400,
            )

        await session.delete(
            departure
        )

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )
@router.post(
    "/tour-categories/{category_id}/archive"
)
async def archive_category(
    category_id: int,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourCategory)
            .where(
                TourCategory.id
                == category_id
            )
        )

        category = (
            result.scalar_one_or_none()
        )

        if category is None:
            return HTMLResponse(
                "Категория не найдена",
                status_code=404,
            )

        category.active = False

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )

@router.post(
    "/tour-categories/{category_id}/delete"
)
async def delete_category(
    category_id: int,
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourCategory)
            .options(
                selectinload(
                    TourCategory.tours
                )
            )
            .where(
                TourCategory.id
                == category_id
            )
        )

        category = (
            result.scalars()
            .unique()
            .one_or_none()
        )

        if category is None:
            return HTMLResponse(
                "Категория не найдена",
                status_code=404,
            )

        if category.tours:
            return HTMLResponse(
                (
                    "Категорию нельзя удалить, "
                    "пока внутри неё есть направления.\n\n"
                    "Сначала удалите направления. "
                    "Если в направлении есть заявки, "
                    "его удалять нельзя — "
                    "используйте архивирование."
                ),
                status_code=400,
            )

        await session.delete(
            category
        )

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )
@router.post(
    "/tours/{tour_id}/archive"
)
async def archive_tour(
    tour_id: int,
    return_to: str = Form("/tours/manage"),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourType)
            .where(
                TourType.id == tour_id
            )
        )

        tour = result.scalar_one_or_none()

        if tour is None:
            return HTMLResponse(
                "Направление не найдено",
                status_code=404,
            )

        tour.active = False

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )


@router.post(
    "/departures/{departure_id}/archive"
)
async def archive_departure(
    departure_id: int,
    return_to: str = Form("/tours/manage"),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourDeparture)
            .where(
                TourDeparture.id
                == departure_id
            )
        )

        departure = (
            result.scalar_one_or_none()
        )

        if departure is None:
            return HTMLResponse(
                "Поездка не найдена",
                status_code=404,
            )

        departure.archived = True
        departure.active = False
        departure.booking_open = False

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )

@router.post(
    "/departures/{departure_id}/restore"
)
async def restore_departure(
    departure_id: int,
    return_to: str = Form("/tours/manage"),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourDeparture)
            .where(
                TourDeparture.id
                == departure_id
            )
        )

        departure = (
            result.scalar_one_or_none()
        )

        if departure is None:
            return HTMLResponse(
                "Поездка не найдена",
                status_code=404,
            )

        departure.archived = False
        departure.active = True
        departure.booking_open = (
            departure.end_date
            >= date.today()
        )

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )


# =========================
# ФОТОГРАФИИ
# =========================


async def prepare_photo_uploads(
    photos: list[UploadFile],
) -> list[tuple[UploadFile, str]]:
    prepared: list[
        tuple[UploadFile, str]
    ] = []

    if not photos:
        raise ValueError(
            "Выбери хотя бы одно фото"
        )

    if len(photos) > MAX_PHOTO_BATCH_COUNT:
        raise ValueError("За один раз можно загрузить не больше 5 фото")
    if sum(photo.size or 0 for photo in photos) > MAX_PHOTO_BATCH_BYTES:
        raise ValueError("Общий размер фотографий должен быть не больше 20 МБ")

    total_size = 0
    for photo in photos:
        data_url = (
            await upload_to_data_url(
                photo
            )
        )

        # Account for actual bytes as well, including uploads with unknown size.
        encoded_length = len(data_url) - data_url.index(",") - 1
        padding = 2 if data_url.endswith("==") else int(data_url.endswith("="))
        total_size += encoded_length // 4 * 3 - padding
        if total_size > MAX_PHOTO_BATCH_BYTES:
            raise ValueError("Общий размер фотографий должен быть не больше 20 МБ")

        prepared.append(
            (
                photo,
                data_url,
            )
        )

    return prepared


@router.post(
    "/about/media/add"
)
async def add_about_media(
    photos: list[UploadFile] = File(...),
):
    try:
        prepared = (
            await prepare_photo_uploads(
                photos
            )
        )
    except ValueError as error:
        return HTMLResponse(
            str(error),
            status_code=400,
        )

    async with SessionLocal() as session:
        max_order_result = (
            await session.execute(
                select(
                    func.max(
                        TourMedia.sort_order
                    )
                )
                .where(
                    TourMedia.category_id
                    .is_(None),
                    TourMedia.tour_id
                    .is_(None),
                    TourMedia.section
                    == "about",
                )
            )
        )

        next_order = (
            (
                max_order_result
                .scalar_one()
                or 0
            )
            + 10
        )

        for photo, data_url in prepared:
            session.add(
                TourMedia(
                    category_id=None,
                    tour_id=None,
                    section="about",
                    media_type="photo",
                    title=photo.filename,
                    url=data_url,
                    sort_order=next_order,
                    active=True,
                )
            )

            next_order += 10

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )


@router.post(
    "/tour-categories/{category_id}/media/add"
)
async def add_category_media(
    category_id: int,
    photos: list[UploadFile] = File(...),
):
    try:
        prepared = (
            await prepare_photo_uploads(
                photos
            )
        )
    except ValueError as error:
        return HTMLResponse(
            str(error),
            status_code=400,
        )

    async with SessionLocal() as session:
        category_result = (
            await session.execute(
                select(TourCategory)
                .where(
                    TourCategory.id
                    == category_id
                )
            )
        )

        category = (
            category_result
            .scalar_one_or_none()
        )

        if category is None:
            return HTMLResponse(
                "Категория не найдена",
                status_code=404,
            )

        max_order_result = (
            await session.execute(
                select(
                    func.max(
                        TourMedia.sort_order
                    )
                )
                .where(
                    TourMedia.category_id
                    == category_id,
                    TourMedia.tour_id
                    .is_(None),
                    TourMedia.section
                    == "category",
                )
            )
        )

        next_order = (
            (
                max_order_result
                .scalar_one()
                or 0
            )
            + 10
        )

        for photo, data_url in prepared:
            session.add(
                TourMedia(
                    category_id=category.id,
                    tour_id=None,
                    section="category",
                    media_type="photo",
                    title=photo.filename,
                    url=data_url,
                    sort_order=next_order,
                    active=True,
                )
            )

            next_order += 10

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )


@router.post(
    "/tours/{tour_id}/media/add"
)
async def add_tour_media(
    tour_id: int,
    section: str = Form(...),
    photos: list[UploadFile] = File(...),
    return_to: str = Form("/tours/manage"),
):
    if section not in {
        "accommodation",
        "activity",
    }:
        return HTMLResponse(
            "Некорректный раздел фотографий",
            status_code=400,
        )

    try:
        prepared = (
            await prepare_photo_uploads(
                photos
            )
        )
    except ValueError as error:
        return HTMLResponse(
            str(error),
            status_code=400,
        )

    async with SessionLocal() as session:
        tour_result = (
            await session.execute(
                select(TourType)
                .where(
                    TourType.id == tour_id
                )
            )
        )

        tour = (
            tour_result
            .scalar_one_or_none()
        )

        if tour is None:
            return HTMLResponse(
                "Направление не найдено",
                status_code=404,
            )

        max_order_result = (
            await session.execute(
                select(
                    func.max(
                        TourMedia.sort_order
                    )
                )
                .where(
                    TourMedia.tour_id
                    == tour_id,
                    TourMedia.section
                    == section,
                )
            )
        )

        next_order = (
            (
                max_order_result
                .scalar_one()
                or 0
            )
            + 10
        )

        for photo, data_url in prepared:
            session.add(
                TourMedia(
                    category_id=None,
                    tour_id=tour.id,
                    section=section,
                    media_type="photo",
                    title=photo.filename,
                    url=data_url,
                    sort_order=next_order,
                    active=True,
                )
            )

            next_order += 10

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )


@router.post(
    "/media/reorder"
)
async def reorder_media(
    request: Request,
):
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(
            {
                "ok": False,
                "error":
                    "Некорректные данные",
            },
            status_code=400,
        )

    media_ids = payload.get(
        "media_ids",
        []
    )

    if (
        not isinstance(media_ids, list)
        or not media_ids
    ):
        return JSONResponse(
            {
                "ok": False,
                "error":
                    "Список фото пуст",
            },
            status_code=400,
        )

    try:
        normalized_ids = [
            int(media_id)
            for media_id in media_ids
        ]
    except (
        TypeError,
        ValueError,
    ):
        return JSONResponse(
            {
                "ok": False,
                "error":
                    "Некорректные ID фото",
            },
            status_code=400,
        )

    if len(
        set(normalized_ids)
    ) != len(normalized_ids):
        return JSONResponse(
            {
                "ok": False,
                "error":
                    "Повторяющиеся ID фото",
            },
            status_code=400,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourMedia).options(defer(TourMedia.url))
            .where(
                TourMedia.id.in_(
                    normalized_ids
                )
            )
        )

        items = list(
            result.scalars().all()
        )

        if len(items) != len(
            normalized_ids
        ):
            return JSONResponse(
                {
                    "ok": False,
                    "error":
                        "Одно из фото не найдено",
                },
                status_code=404,
            )

        first = items[0]

        scope = (
            first.category_id,
            first.tour_id,
            first.section,
        )

        if any(
            (
                item.category_id,
                item.tour_id,
                item.section,
            )
            != scope
            for item in items
        ):
            return JSONResponse(
                {
                    "ok": False,
                    "error":
                        "Нельзя смешивать разные галереи",
                },
                status_code=400,
            )

        items_by_id = {
            item.id: item
            for item in items
        }

        for index, media_id in enumerate(
            normalized_ids,
            start=1,
        ):
            items_by_id[
                media_id
            ].sort_order = (
                index * 10
            )

        await session.commit()

    return JSONResponse(
        {
            "ok": True,
        }
    )


@router.post(
    "/media/{media_id}/move"
)
async def move_media(
    media_id: int,
    direction: str = Form(...),
):
    if direction not in {"up", "down"}:
        return HTMLResponse(
            "Некорректное направление сортировки",
            status_code=400,
        )

    async with SessionLocal() as session:
        result = await session.execute(
            select(TourMedia).options(defer(TourMedia.url))
            .where(
                TourMedia.id == media_id
            )
        )

        media = result.scalar_one_or_none()

        if media is None:
            return HTMLResponse(
                "Фото не найдено",
                status_code=404,
            )

        scope_conditions = [
            TourMedia.section
            == media.section,
        ]

        if media.category_id is None:
            scope_conditions.append(
                TourMedia.category_id
                .is_(None)
            )
        else:
            scope_conditions.append(
                TourMedia.category_id
                == media.category_id
            )

        if media.tour_id is None:
            scope_conditions.append(
                TourMedia.tour_id
                .is_(None)
            )
        else:
            scope_conditions.append(
                TourMedia.tour_id
                == media.tour_id
            )

        siblings_result = await session.execute(
            select(TourMedia).options(defer(TourMedia.url))
            .where(*scope_conditions)
            .order_by(
                TourMedia.sort_order,
                TourMedia.id,
            )
        )

        siblings = list(
            siblings_result.scalars().all()
        )

        if len(siblings) < 2:
            return RedirectResponse(
                url="/tours/manage",
                status_code=303,
            )

        # Нормализуем порядок, чтобы даже старые одинаковые sort_order
        # корректно переставлялись кнопками вверх/вниз.
        for index, item in enumerate(
            siblings,
            start=1,
        ):
            item.sort_order = index * 10

        current_index = next(
            (
                index
                for index, item
                in enumerate(siblings)
                if item.id == media.id
            ),
            None,
        )

        if current_index is None:
            return HTMLResponse(
                "Фото не найдено в галерее",
                status_code=404,
            )

        target_index = (
            current_index - 1
            if direction == "up"
            else current_index + 1
        )

        if 0 <= target_index < len(siblings):
            current = siblings[current_index]
            target = siblings[target_index]

            current.sort_order, target.sort_order = (
                target.sort_order,
                current.sort_order,
            )

        await session.commit()

    return RedirectResponse(
        url="/tours/manage",
        status_code=303,
    )


@router.post(
    "/media/{media_id}/toggle"
)
async def toggle_media(
    media_id: int,
    return_to: str = Form("/tours/manage"),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourMedia).options(defer(TourMedia.url))
            .where(
                TourMedia.id == media_id
            )
        )

        media = (
            result.scalar_one_or_none()
        )

        if media is None:
            return HTMLResponse(
                "Фото не найдено",
                status_code=404,
            )

        media.active = not media.active

        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )


@router.post(
    "/media/{media_id}/delete"
)
async def delete_media(
    media_id: int,
    return_to: str = Form("/tours/manage"),
):
    async with SessionLocal() as session:
        result = await session.execute(
            select(TourMedia).options(defer(TourMedia.url))
            .where(
                TourMedia.id == media_id
            )
        )

        media = (
            result.scalar_one_or_none()
        )

        if media is None:
            return HTMLResponse(
                "Фото не найдено",
                status_code=404,
            )

        await session.delete(media)
        await session.commit()

    return RedirectResponse(
        url=return_to,
        status_code=303,
    )
