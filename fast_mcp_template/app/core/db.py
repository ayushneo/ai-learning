"""Async SQLAlchemy engine/session, wired through lifespan state.

# tip 6 (fastapi-tips/Kludex): use *lifespan state* (the dict you `yield` from
# the lifespan context manager), not `app.state`. app.state is untyped and
# global; lifespan state flows through `request.state` and is what FastAPI's
# own docs now recommend. See app/main.py for where this is yielded.
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings


class State(TypedDict):
    db_engine: AsyncEngine
    db_sessionmaker: async_sessionmaker[AsyncSession]


@asynccontextmanager
async def db_lifespan() -> AsyncIterator[State]:
    settings = get_settings()
    engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # cheap SELECT 1 before reuse; catches DB restarts/dropped conns
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield {"db_engine": engine, "db_sessionmaker": sessionmaker}
    finally:
        await engine.dispose()
