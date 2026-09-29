"""Item routes. Plain functions + Depends, not class-based controllers.

fast-api-docker-poetry (one of this template's references) uses fastapi-restful's
`@cbv` to share `__init__`-built dependencies across methods on a class. Skipped
here: FastAPI's own `Depends()` already shares a constructed object across
routes without a third-party decorator or a new class per resource -- reach
for `@cbv` if a resource genuinely needs shared *mutable* per-request state
across several methods, not by default.
"""
import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import get_item_service
from app.schemas.item import ItemCreate, ItemRead
from app.services.item import ItemService

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
async def create_item(data: ItemCreate, service: ItemService = Depends(get_item_service)) -> ItemRead:
    item = await service.create(data)
    return ItemRead.model_validate(item)


@router.get("/{item_id}", response_model=ItemRead)
async def get_item(item_id: uuid.UUID, service: ItemService = Depends(get_item_service)) -> ItemRead:
    item = await service.get(item_id)
    return ItemRead.model_validate(item)


@router.get("", response_model=list[ItemRead])
async def list_items(
    limit: int = 50,
    offset: int = 0,
    service: ItemService = Depends(get_item_service),
) -> list[ItemRead]:
    items = await service.list(limit=limit, offset=offset)
    return [ItemRead.model_validate(item) for item in items]


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: uuid.UUID, service: ItemService = Depends(get_item_service)) -> None:
    await service.delete(item_id)
