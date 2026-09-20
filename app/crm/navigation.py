import re

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy import func, select

from app.database.models import Booking
from app.database.session import SessionLocal


class CRMNavigationMiddleware(
    BaseHTTPMiddleware
):
    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        response = await call_next(request)

        # The login page intentionally has no CRM navigation.
        if request.url.path == "/login":
            return response

        if request.method != "GET":
            return response

        content_type = response.headers.get(
            "content-type",
            "",
        )

        if "text/html" not in content_type:
            return response

        body = b""

        async for chunk in response.body_iterator:
            body += chunk

        try:
            html = body.decode("utf-8")
        except UnicodeDecodeError:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=content_type,
            )

        new_bookings_count = 0

        try:
            async with SessionLocal() as session:
                result = await session.execute(
                    select(
                        func.count(
                            Booking.id
                        )
                    ).where(
                        Booking.status
                        == "Новая"
                    )
                )

                new_bookings_count = (
                    result.scalar_one()
                    or 0
                )
        except Exception:
            # Навигация не должна ломать CRM,
            # даже если счётчик временно
            # не удалось получить.
            new_bookings_count = 0

        html = inject_navigation(
            html=html,
            path=request.url.path,
            new_bookings_count=(
                new_bookings_count
            ),
        )

        headers = dict(
            response.headers
        )
        headers.pop(
            "content-length",
            None,
        )

        return Response(
            content=html,
            status_code=response.status_code,
            headers=headers,
            media_type=None,
        )


def inject_navigation(
    *,
    html: str,
    path: str,
    new_bookings_count: int,
) -> str:
    if "<body" not in html.lower():
        return html

    # Убираем старую шапку конкретной
    # страницы, чтобы навигация была одна.
    html = re.sub(
        r'<header\s+class=["\']header["\']'
        r'[^>]*>.*?</header>',
        "",
        html,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if (
        "/static/crm_nav.css"
        not in html
    ):
        html = re.sub(
            r"</head>",
            (
                '<link rel="stylesheet" '
                'href="/static/crm_nav.css">'
                "</head>"
            ),
            html,
            count=1,
            flags=re.IGNORECASE,
        )

    nav_html = build_navigation_html(
        path=path,
        new_bookings_count=(
            new_bookings_count
        ),
    )

    html = re.sub(
        r"(<body[^>]*>)",
        r"\1" + nav_html,
        html,
        count=1,
        flags=re.IGNORECASE,
    )

    return html


def build_navigation_html(
    *,
    path: str,
    new_bookings_count: int,
) -> str:
    def active(
        section: str,
    ) -> str:
        if (
            section == "home"
            and path == "/"
        ):
            return " is-active"

        if (
            section == "bookings"
            and (
                path.startswith(
                    "/bookings"
                )
                or path.startswith(
                    "/customers"
                )
            )
        ):
            return " is-active"

        if (
            section == "tours"
            and (
                path.startswith(
                    "/tours"
                )
                or (
                    path.startswith(
                        "/departures/"
                    )
                    and not path.endswith(
                        "/finance"
                    )
                )
            )
        ):
            return " is-active"

        if (
            section == "finance"
            and (
                path == "/finance"
                or path.endswith(
                    "/finance"
                )
            )
        ):
            return " is-active"

        return ""

    badge = ""

    if new_bookings_count > 0:
        badge = (
            '<span class="crm-nav-badge">'
            f"{new_bookings_count}"
            "</span>"
        )

    return f"""
<header class="crm-global-header">
    <a
        class="crm-global-brand"
        href="/"
    >
        <span class="crm-global-logo">
            WOWDERTOUR
        </span>
        <span class="crm-global-subtitle">
            CRM
        </span>
    </a>

    <nav class="crm-global-nav">
        <a
            class="crm-nav-link{active('home')}"
            href="/"
        >
            🏠 Главная
        </a>

        <a
            class="crm-nav-link{active('bookings')}"
            href="/bookings"
        >
            📋 Заявки
            {badge}
        </a>

        <a
            class="crm-nav-link{active('tours')}"
            href="/tours/manage"
        >
            🗺 Туры
        </a>

        <a
            class="crm-nav-link{active('finance')}"
            href="/finance"
        >
            💰 Финансы
        </a>

        <form class="crm-nav-logout-form" method="post" action="/logout">
            <button class="crm-nav-logout" type="submit" title="Выйти из CRM">
                ↪ Выйти
            </button>
        </form>
    </nav>
</header>
"""
