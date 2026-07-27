"""Per-IP rate limiter with endpoint-specific limits and X-Forwarded-For validation."""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP in-memory rate limiter with endpoint-specific tiers.

    Uses request.client.host (the TCP-level peer address from nginx) instead
    of X-Forwarded-For to prevent header-spoofing bypass.
    """

    # Endpoint-specific limits: (requests_per_minute, window_seconds)
    TIERS = {
        '/api/auth/login':           (10, 60),
        '/api/auth/register':        (5, 60),
        '/api/auth/forgot-password': (5, 60),
        '/api/auth/reset-password':  (5, 60),
        '/api/payments/initialize':  (10, 60),
        '/api/payments/webhook':     (60, 60),
        '/api/payments/verify':      (15, 60),
        '/api/payments/retry':       (10, 60),
        '/api/orders/track':         (10, 60),
        '/api/coupons/validate':     (20, 60),
        '/api/newsletters/subscribe':(10, 60),
    }

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.default_rpm = requests_per_minute
        self.window = 60.0
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        # Use the TCP-level client address (set by nginx as the real peer IP).
        # Do NOT read X-Forwarded-For here -- nginx already sets
        # X-Real-IP / X-Forwarded-For and the rate limiter should use the
        # direct connection IP to prevent header-spoofing bypass.
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    def _get_limit(self, path: str) -> int:
        # Exact match first, then prefix match
        if path in self.TIERS:
            return self.TIERS[path][0]
        for prefix, (limit, _) in self.TIERS.items():
            if path.startswith(prefix):
                return limit
        return self.default_rpm

    def _get_window(self, path: str) -> float:
        if path in self.TIERS:
            return float(self.TIERS[path][1])
        return self.window

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Skip rate limiting for static files and health checks
        if path.startswith('/static') or path == '/health':
            return await call_next(request)

        ip = self._client_ip(request)
        key = f"{ip}:{path}"
        now = time.monotonic()
        window = self._get_window(path)
        limit = self._get_limit(path)

        # Prune timestamps outside the window
        self._hits[key] = [t for t in self._hits[key] if now - t < window]

        if len(self._hits[key]) >= limit:
            retry_after = int(window - (now - self._hits[key][0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        self._hits[key].append(now)
        remaining = limit - len(self._hits[key])

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        return response
