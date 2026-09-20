from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.crm.auth import (
    CRMAuthMiddleware,
    router as auth_router,
)
from app.crm.accommodation import (
    router as accommodation_router,
)
from app.crm.finance import (
    router as finance_router,
)
from app.crm.navigation import (
    CRMNavigationMiddleware,
)
from app.crm.pricing import (
    router as pricing_router,
)
from app.crm.routes import (
    router as crm_router,
)
from app.crm.tours import (
    router as tours_router,
)


BASE_DIR = Path(__file__).resolve().parent


app = FastAPI(
    title="WowderTour CRM",
)


templates = Jinja2Templates(
    directory=str(
        BASE_DIR / "templates"
    )
)

app.state.templates = templates


app.mount(
    "/static",
    StaticFiles(
        directory=str(
            BASE_DIR / "static"
        )
    ),
    name="static",
)


app.add_middleware(
    CRMNavigationMiddleware
)

# Added after navigation so it becomes the outer middleware and
# unauthenticated requests never reach CRM/database handlers.
app.add_middleware(
    CRMAuthMiddleware
)

app.include_router(auth_router)


app.include_router(
    crm_router
)

app.include_router(
    accommodation_router
)

app.include_router(
    finance_router
)

app.include_router(
    pricing_router
)

app.include_router(
    tours_router
)
