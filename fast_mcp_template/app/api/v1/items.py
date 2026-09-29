"""Item routes. Plain functions + Depends, not class-based controllers.

fast-api-docker-poetry (one of fastapi_template's references) uses fastapi-restful's
`@cbv` to share `__init__`-built dependencies across methods on a class. Skipped
here: FastAPI's own `Depends()` already shares a constructed object across
routes without a third-party decorator or a new class per resource -- reach
for `@cbv` if a resource genuinely needs shared *mutable* per-request state
across several methods, not by default.

`operation_id` is set explicitly on every route. fastapi_mcp uses the
operation_id as the MCP tool's name -- leave it to FastAPI's auto-generated
one (a function-name/path hash) and an unrelated refactor (renaming the
function, moving the router) silently renames or breaks the tool from an
agent's perspective. This is the single most-flagged gotcha across every
fastapi_mcp write-up surveyed for this template; it's cheap to just always do.
"""
import uuid

from fastapi import APIRouter, Depends, status

from app.api.deps import get_item_service
from app.schemas.item import ItemCreate, ItemRead
from app.services.item import ItemService

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED, operation_id="create_item")
async def create_item(data: ItemCreate, service: ItemService = Depends(get_item_service)) -> ItemRead:
    item = await service.create(data)
    return ItemRead.model_validate(item)


@router.get("/{item_id}", response_model=ItemRead, operation_id="get_item")
async def get_item(item_id: uuid.UUID, service: ItemService = Depends(get_item_service)) -> ItemRead:
    item = await service.get(item_id)
    return ItemRead.model_validate(item)


@router.get("", response_model=list[ItemRead], operation_id="list_items")
async def list_items(
    limit: int = 50,
    offset: int = 0,
    service: ItemService = Depends(get_item_service),
) -> list[ItemRead]:
    items = await service.list(limit=limit, offset=offset)
    return [ItemRead.model_validate(item) for item in items]


# Deliberately NOT exposed as an MCP tool by default -- see app/core/mcp.py's
# `exclude_operations`. A destructive endpoint is a bigger blast radius when
# the caller is an LLM deciding on its own when to invoke it than when it's a
# human clicking a confirm dialog. Still a normal REST endpoint; just opt it
# back in explicitly (remove it from exclude_operations) once that trade-off
# is one you actually want.
@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, operation_id="delete_item")
async def delete_item(item_id: uuid.UUID, service: ItemService = Depends(get_item_service)) -> None:
    await service.delete(item_id)
