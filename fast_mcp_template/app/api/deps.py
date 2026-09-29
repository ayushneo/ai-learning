"""Shared `Depends()` callables -- FastAPI's own DI, nothing more.

# tip 9 (fastapi-tips/Kludex): a non-async dependency runs in a worker
# thread (`run_in_threadpool`), not the event loop. Only 40 threads exist by
# default, so a thread-hungry sync dependency on a hot path can starve the
# app. get_db below is async precisely so it stays on the event loop.

get_db yields one AsyncSession per request and commits on clean exit /
rolls back on exception -- the request is the transaction boundary, which is
the right default for a CRUD API. A use case that must NOT auto-commit
(e.g. a multi-step saga) should manage its own session, not fight this one.
"""
from collections.abc import AsyncIterator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.item import ItemRepository
from app.services.item import ItemService


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    sessionmaker = request.state.db_sessionmaker
    async with sessionmaker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_item_service(session: AsyncSession = Depends(get_db)) -> ItemService:
    return ItemService(ItemRepository(session))
