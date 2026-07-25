"""Global exception handler middleware."""

import logging
import traceback
from typing import Callable

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """Catches unhandled exceptions and returns consistent JSON error responses."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            return await call_next(request)
        except StarletteHTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": str(exc.detail), "status_code": exc.status_code},
            )
        except RequestValidationError as exc:
            errors = []
            for err in exc.errors():
                loc = " -> ".join(str(l) for l in err.get("loc", []))
                errors.append(f"{loc}: {err.get('msg', '')}")
            return JSONResponse(
                status_code=422,
                content={"detail": "; ".join(errors), "status_code": 422},
            )
        except Exception as exc:
            logger.exception("Unhandled exception: %s", exc)
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error", "status_code": 500},
            )


def register_exception_handlers(app):
    """Register per-exception handlers on the FastAPI app instance."""

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={"detail": "Resource not found", "status_code": 404},
        )

    @app.exception_handler(403)
    async def forbidden_handler(request: Request, exc):
        return JSONResponse(
            status_code=403,
            content={"detail": "Forbidden", "status_code": 403},
        )

    @app.exception_handler(401)
    async def unauthorized_handler(request: Request, exc):
        return JSONResponse(
            status_code=401,
            content={"detail": "Unauthorized", "status_code": 401},
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        logger.exception("Internal server error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "status_code": 500},
        )
