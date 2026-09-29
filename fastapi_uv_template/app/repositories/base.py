"""Generic async CRUD repository. One implementation, parameterized by model
type, instead of a get/create/delete trio hand-written per resource -- the
kind of repetition that's worth a small generic for, unlike a one-off value.

Repositories only talk SQLAlchemy. They don't commit -- the caller (usually
a service, sometimes a route for trivial resources) owns the transaction
boundary, so two repository calls can share one commit when a use case spans
more than one table.
"""
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, id_: UUID) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[ModelT]:
        # ponytail: OFFSET/LIMIT pagination -- simplest thing that works, but
        # OFFSET still scans and discards `offset` rows server-side, so cost
        # grows with page depth. Fine well past most APIs' real page counts;
        # switch to keyset pagination (`WHERE id > :last_id ORDER BY id`) if
        # you ever see someone paginating deep into millions of rows.
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    def add(self, instance: ModelT) -> ModelT:
        self.session.add(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.session.delete(instance)
