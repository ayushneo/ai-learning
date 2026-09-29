"""Shared test fixtures.

# tip 10 (fastapi-tips/Kludex): use `pytest.mark.anyio` (anyio is already a
# Starlette dependency) instead of pulling in `pytest-asyncio` separately.
# The `anyio_backend` fixture below pins it to asyncio only -- anyio runs
# each `anyio`-marked test on every configured backend (asyncio *and* trio)
# by default, which is more than an application (as opposed to a library
# meant to support both) needs.
#
# tip 5: HTTPX's AsyncClient over Starlette's TestClient, since the whole
# app is async -- ASGITransport talks to `app` in-process, no real socket.
#
# The DB is swapped for in-memory SQLite via aiosqlite + a dependency
# override, not a real Postgres -- fast, no docker-compose required to run
# `pytest`. Trade-off: SQLite doesn't enforce everything Postgres does
# (e.g. some constraint/type behavior differs). Fine for this template's
# CRUD routes; a project leaning on Postgres-specific features (JSONB,
# advisory locks, ...) should point this at a real Postgres test DB instead.
"""
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.main import app
from app.models.base import Base


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    async with sessionmaker() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_db() -> AsyncIterator[AsyncSession]:
        yield db_session
        await db_session.commit()

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()
