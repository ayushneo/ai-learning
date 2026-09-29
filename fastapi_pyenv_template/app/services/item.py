"""Business logic sits here, not in the route function or the repository.
For CRUD this thin, the service is nearly a pass-through -- that's expected
and fine. The payoff shows up the moment a use case needs more than one
repository call, a permission check, or an outbound call to another system;
the route function still just calls one service method either way.
"""
import uuid

from app.core.exceptions import NotFoundError
from app.models.item import Item
from app.repositories.item import ItemRepository
from app.schemas.item import ItemCreate


class ItemService:
    def __init__(self, repository: ItemRepository) -> None:
        self.repository = repository

    async def create(self, data: ItemCreate) -> Item:
        item = Item(name=data.name, description=data.description)
        self.repository.add(item)
        await self.repository.session.flush()  # populate defaults (id, created_at) without committing yet
        return item

    async def get(self, item_id: uuid.UUID) -> Item:
        item = await self.repository.get(item_id)
        if item is None:
            raise NotFoundError(f"item {item_id} not found")
        return item

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Item]:
        return await self.repository.list(limit=limit, offset=offset)

    async def delete(self, item_id: uuid.UUID) -> None:
        item = await self.get(item_id)
        await self.repository.delete(item)
