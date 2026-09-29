"""App factory + wiring. Run with FastAPI CLI (github.com/fastapi/fastapi-cli),
which `pip install "fastapi[standard]"` already gives you as the `fastapi`
command -- no hand-rolled `if __name__ == "__main__": uvicorn.run(...)` needed:

    fastapi dev app/main.py     # dev: reload on, binds 127.0.0.1, sets FASTAPI_ENV=development
    fastapi run app/main.py     # prod: reload off, binds 0.0.0.0 (put a real proxy/TLS in front)

See Makefile for the wrapped versions of both.
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as v1_router
from app.core.config import get_settings
from app.core.db import State, db_lifespan
from app.core.exceptions import AppError, app_error_handler
from app.core.logging import configure_logging
from app.core.mcp import mount_mcp
from app.middleware.request_id import RequestIDMiddleware

settings = get_settings()
configure_logging(settings.log_level)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[State]:
    async with db_lifespan() as state:
        yield state


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# tip 1 (fastapi-tips/Kludex): install uvloop + httptools (see pyproject's
# `fastapi[standard]` extra) -- Uvicorn picks them up automatically, no code
# change needed here. Skipped on Windows dev machines: uvloop isn't
# available there; `fastapi[standard]` handles that via its own env markers.

app.add_middleware(RequestIDMiddleware)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_exception_handler(AppError, app_error_handler)

app.include_router(v1_router)


@app.get("/health", tags=["health"], operation_id="health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Mounted last: fastapi_mcp snapshots the app's OpenAPI schema (and therefore
# every operation_id) at construction time, so every route above must exist
# before this call, or it silently won't become a tool.
mount_mcp(app)
