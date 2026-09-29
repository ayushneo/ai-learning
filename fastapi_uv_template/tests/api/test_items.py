import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.anyio


async def test_create_and_get_item(client: AsyncClient) -> None:
    create_resp = await client.post("/v1/items", json={"name": "widget", "description": "a widget"})
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    get_resp = await client.get(f"/v1/items/{item_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "widget"


async def test_get_missing_item_404s(client: AsyncClient) -> None:
    resp = await client.get("/v1/items/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


async def test_list_items(client: AsyncClient) -> None:
    await client.post("/v1/items", json={"name": "a"})
    await client.post("/v1/items", json={"name": "b"})

    resp = await client.get("/v1/items")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


async def test_delete_item(client: AsyncClient) -> None:
    create_resp = await client.post("/v1/items", json={"name": "to-delete"})
    item_id = create_resp.json()["id"]

    delete_resp = await client.delete(f"/v1/items/{item_id}")
    assert delete_resp.status_code == 204

    get_resp = await client.get(f"/v1/items/{item_id}")
    assert get_resp.status_code == 404


async def test_health_check(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
