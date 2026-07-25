"""Simple in-memory rate limiter middleware."""

import time
from collections import defaultdict
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP in-memory rate limiter.

    Tracks request timestamps in a dict keyed by client IP and rejects
    requests that exceed the configured threshold within a rolling window.
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window = 60.0  # seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def _client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        ip = self._client_ip(request)
        now = time.monotonic()

        # Prune timestamps outside the window
        self._hits[ip] = [t for t in self._hits[ip] if now - t < self.window]

        if len(self._hits[ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Try again later."},
                headers={
                    "Retry-After": str(int(self.window)),
                    "X-RateLimit-Limit": str(self.requests_per_minute),
                    "X-RateLimit-Remaining": "0",
                },
            )

        self._hits[ip].append(now)
        remaining = self.requests_per_minute - len(self._hits[ip])

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(max(remaining, 0))
        return response
