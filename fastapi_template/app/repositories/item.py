from app.models.item import Item
from app.repositories.base import BaseRepository


class ItemRepository(BaseRepository[Item]):
    model = Item
