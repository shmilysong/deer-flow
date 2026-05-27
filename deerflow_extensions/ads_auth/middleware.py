import json
import logging
from typing import Awaitable, Callable

from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

_PUBLIC_PREFIXES = ("/health", "/docs", "/redoc", "/openapi.json")

_PUBLIC_EXACT = frozenset({
    "/api/v1/auth/login/ads",
    "/api/v1/auth/logout",
})

_BLOCKED_AUTH_ENDPOINTS = frozenset({
    "/api/v1/auth/login/local",
    "/api/v1/auth/register",
    "/api/v1/auth/initialize",
})

_REDIRECT_ENDPOINTS = frozenset({
    "/api/v1/auth/setup-status",
})


class ADSProxyMiddleware:
    """ASGI-level middleware that runs before Starlette's BaseHTTPMiddleware stack.

    Uses raw ASGI interface (scope/receive/send) instead of BaseHTTPMiddleware
    so that modifications to ``scope`` are visible to ALL downstream middleware.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "").rstrip("/")

        if any(path.startswith(p) for p in _PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        if path in _PUBLIC_EXACT:
            await self.app(scope, receive, send)
            return

        if path in _BLOCKED_AUTH_ENDPOINTS:
            response = JSONResponse(
                status_code=410,
                content={"detail": {"message": "已替换为 ADS 认证，请使用 POST /api/v1/auth/login/ads"}},
            )
            await response(scope, receive, send)
            return

        if path in _REDIRECT_ENDPOINTS:
            response = JSONResponse(
                status_code=200,
                content={"needs_setup": False},
            )
            await response(scope, receive, send)
            return

        # Extract cookies from the raw scope headers
        ads_token = _get_cookie(scope, "ads_token") or _get_cookie(scope, "access_token")
        if not ads_token:
            response = JSONResponse(
                status_code=401,
                content={"detail": {"message": "未认证，请使用 ADS 账号登录"}},
            )
            await response(scope, receive, send)
            return

        try:
            payload = _decode_jwt(ads_token)
            username = payload.get("username", "unknown")
        except Exception:
            response = JSONResponse(
                status_code=401,
                content={"detail": {"message": "ADS token 无效或已过期，请重新登录"}},
            )
            await response(scope, receive, send)
            return

        from app.gateway.auth.models import User

        user = User(
            email=f"{username}@example.com",
            system_role="user",
        )

        # Stamp the ASGI scope so ALL downstream middleware (including
        # Starlette's BaseHTTPMiddleware layers) can see it
        scope["_ads_authenticated"] = True
        scope["ads_user"] = user

        await self.app(scope, receive, send)


def _get_cookie(scope: dict, name: str) -> str | None:
    """Extract a single cookie from the ASGI scope headers."""
    for key, val in scope.get("headers", []):
        if key == b"cookie":
            cookies = val.decode()
            for c in cookies.split(";"):
                c = c.strip()
                if c.startswith(f"{name}="):
                    return c[len(name) + 1:]
    return None


def _decode_jwt(token: str) -> dict:
    import base64
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid JWT format")
    payload = parts[1]
    padded = payload + "=" * (4 - len(payload) % 4)
    decoded = base64.urlsafe_b64decode(padded)
    return json.loads(decoded)
