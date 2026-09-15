"""
Lightweight PIN gate for the API.

Single-user personal app: if `dashboard_pin` is set, every /api/* request must
carry the PIN in the `X-Dashboard-Pin` header. When the setting is empty the gate
is disabled and the API is open (preserving the original behaviour).

This is intentionally simple — a shared secret, not per-user auth. It exists so the
dashboard can be exposed on a public Replit URL without leaking financial data to
anyone who knows the address. Pair it with HTTPS (Replit provides it) so the header
isn't sent in the clear.
"""

import logging
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

PIN_HEADER = "X-Dashboard-Pin"

# Paths that must stay open even when the gate is on:
#   /health         — lets the frontend discover whether a PIN is required
#   /docs, /openapi — FastAPI docs (still localhost-only once port 8000 is closed)
_OPEN_PREFIXES = ("/health", "/docs", "/openapi.json", "/redoc")


class PinAuthMiddleware(BaseHTTPMiddleware):
    """Reject /api/* requests that lack the correct PIN header."""

    def __init__(self, app, pin: str):
        super().__init__(app)
        self._pin = pin or ""
        # FOOTGUN GUARD: empty pin == dashboard is completely OPEN (no auth).
        # Loudly log so nobody ships this publicly by accident.
        if not self._pin:
            logger.warning(
                "DASHBOARD_PIN is EMPTY — the dashboard PIN gate is DISABLED and "
                "the /api/* endpoints are OPEN (no authentication). Financial data "
                "is readable by anyone with the URL. Set a strong DASHBOARD_PIN in "
                ".env / Replit Secrets before exposing this app publicly."
            )

    async def dispatch(self, request: Request, call_next):
        # Gate disabled → behave exactly as before.
        if not self._pin:
            return await call_next(request)

        path = request.url.path
        if path.startswith(_OPEN_PREFIXES):
            return await call_next(request)

        # Only guard the API surface; static assets are served by the Vite layer.
        if not path.startswith("/api/"):
            return await call_next(request)

        # Allow CORS preflight through — it never carries custom headers.
        if request.method == "OPTIONS":
            return await call_next(request)

        supplied = request.headers.get(PIN_HEADER, "")
        # Constant-time compare so a wrong PIN can't be timing-guessed.
        if not secrets.compare_digest(supplied, self._pin):
            return JSONResponse(
                {"detail": "Missing or invalid dashboard PIN."},
                status_code=401,
                headers={"WWW-Authenticate": PIN_HEADER},
            )

        return await call_next(request)
