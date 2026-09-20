from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings


router = APIRouter()

COOKIE_NAME = "wowdertour_crm_session"
PUBLIC_PATHS = {"/login", "/favicon.ico"}
PUBLIC_PREFIXES = ("/static/",)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def auth_is_configured() -> bool:
    return bool(
        settings.crm_username
        and settings.crm_password
        and settings.crm_secret_key
        and len(settings.crm_secret_key) >= 32
    )


def create_session_token(username: str) -> str:
    payload = {
        "u": username,
        "exp": int(time.time()) + settings.crm_session_hours * 3600,
    }
    payload_raw = json.dumps(
        payload,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    payload_encoded = _b64encode(payload_raw)
    signature = hmac.new(
        settings.crm_secret_key.encode("utf-8"),
        payload_encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_encoded}.{_b64encode(signature)}"


def verify_session_token(token: str | None) -> str | None:
    if not token or not auth_is_configured():
        return None

    try:
        payload_encoded, signature_encoded = token.split(".", 1)
        expected_signature = hmac.new(
            settings.crm_secret_key.encode("utf-8"),
            payload_encoded.encode("ascii"),
            hashlib.sha256,
        ).digest()
        supplied_signature = _b64decode(signature_encoded)

        if not hmac.compare_digest(expected_signature, supplied_signature):
            return None

        payload = json.loads(_b64decode(payload_encoded).decode("utf-8"))
        username = str(payload.get("u", ""))
        expires_at = int(payload.get("exp", 0))

        if expires_at <= int(time.time()):
            return None

        if not hmac.compare_digest(username, settings.crm_username):
            return None

        return username
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _safe_next(value: str | None) -> str:
    if not value:
        return "/"
    if not value.startswith("/") or value.startswith("//"):
        return "/"
    return value


def _cookie_secure(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return bool(
        settings.crm_cookie_secure
        or request.url.scheme == "https"
        or forwarded_proto.split(",", 1)[0].strip().lower() == "https"
    )


class CRMAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in PUBLIC_PATHS or path.startswith(PUBLIC_PREFIXES):
            return await call_next(request)

        if not auth_is_configured():
            return HTMLResponse(
                "CRM authorization is not configured. Set CRM_USERNAME, "
                "CRM_PASSWORD and CRM_SECRET_KEY (at least 32 characters).",
                status_code=503,
            )

        username = verify_session_token(request.cookies.get(COOKIE_NAME))
        if username is None:
            next_path = path
            if request.url.query:
                next_path += f"?{request.url.query}"
            return RedirectResponse(
                url=f"/login?next={quote(next_path, safe='/?:=&')}",
                status_code=303,
            )

        request.state.crm_username = username
        response = await call_next(request)
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    if not auth_is_configured():
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": (
                    "Авторизация не настроена. Добавьте CRM_USERNAME, "
                    "CRM_PASSWORD и CRM_SECRET_KEY (минимум 32 символа)."
                ),
                "next": "/",
                "configured": False,
            },
            status_code=503,
        )

    if verify_session_token(request.cookies.get(COOKIE_NAME)):
        return RedirectResponse(url=_safe_next(next), status_code=303)

    return request.app.state.templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": None,
            "next": _safe_next(next),
            "configured": True,
        },
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
):
    if not auth_is_configured():
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": (
                    "Авторизация не настроена. Добавьте CRM_USERNAME, "
                    "CRM_PASSWORD и CRM_SECRET_KEY (минимум 32 символа)."
                ),
                "next": "/",
                "configured": False,
            },
            status_code=503,
        )

    username_ok = hmac.compare_digest(username.strip(), settings.crm_username)
    password_ok = hmac.compare_digest(password, settings.crm_password)

    if not (username_ok and password_ok):
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Неверный логин или пароль.",
                "next": _safe_next(next),
                "configured": True,
            },
            status_code=401,
        )

    response = RedirectResponse(url=_safe_next(next), status_code=303)
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_session_token(settings.crm_username),
        max_age=settings.crm_session_hours * 3600,
        httponly=True,
        secure=_cookie_secure(request),
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=_cookie_secure(request),
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return response
