"""Domain exceptions + a handler registered once in main.py.

Trade-off: raising a plain HTTPException everywhere is fewer lines, but it
couples the service/repository layers (which shouldn't know about HTTP) to
FastAPI. A small typed exception hierarchy + one exception_handler at the
edge keeps "not found" a domain concept and "404" an HTTP concern. Worth it
past ~2-3 resources; for a single-endpoint toy, HTTPException directly is
fine and this is overkill -- see fast-api-docker-poetry's own README for the
same trade-off (they made the same call at controller-count > 1).
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "Resource conflict"


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
