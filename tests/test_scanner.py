"""Real endpoint route validation replaces the nonexistent scanner handlers."""

import pytest
from sqlalchemy import select

from app.models.endpoint import Endpoint
from tests.test_endpoint_asgi import api_db as api_db


@pytest.mark.asyncio
async def test_created_endpoint_is_visible_in_listing(api_db):
    client, _, _ = api_db
    created = await client.post(
        "/api/v1/endpoints", json={"name": "local", "url": "https://local.invalid"}
    )
    assert created.status_code == 201, created.text
    listed = await client.get("/api/v1/endpoints")
    assert listed.status_code == 200
    assert listed.json() == {"endpoints": [created.json()], "total": 1}
    assert created.json()["method"] == "GET"
    assert created.json()["expected_status"] == 200
    assert created.json()["is_active"] is True


@pytest.mark.asyncio
async def test_duplicate_name_returns_400_without_changing_database(api_db):
    client, sessions, _ = api_db
    payload = {"name": "local", "url": "https://local.invalid"}
    assert (await client.post("/api/v1/endpoints", json=payload)).status_code == 201
    response = await client.post("/api/v1/endpoints", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
    async with sessions() as db:
        assert len((await db.execute(select(Endpoint))).scalars().all()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "patch",
    [
        {"name": ""},
        {"name": None},
        {"interval": 9},
        {"timeout": 0},
        {"expected_status": 99},
        {"expected_status": 600},
    ],
)
async def test_invalid_create_returns_422_without_persisting(api_db, patch):
    client, sessions, _ = api_db
    payload = {"name": "valid_input", "url": "https://local.invalid", **patch}
    response = await client.post("/api/v1/endpoints", json=payload)
    assert response.status_code == 422, response.text
    assert any(error["loc"][-1] in patch for error in response.json()["detail"])
    async with sessions() as db:
        assert (await db.execute(select(Endpoint))).scalars().all() == []


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["get", "put", "delete"])
async def test_missing_endpoint_has_json_404(api_db, method):
    client, _, _ = api_db
    kwargs = {"json": {"name": "valid"}} if method == "put" else {}
    response = await getattr(client, method)("/api/v1/endpoints/999", **kwargs)
    assert response.status_code == 404
    assert response.json() == {"detail": "Endpoint 999 not found"}
    assert response.headers["x-request-id"]


@pytest.mark.asyncio
async def test_unfiltered_total_is_not_page_size(api_db):
    client, sessions, _ = api_db
    async with sessions() as db:
        db.add_all(
            [
                Endpoint(name="active", url="https://a.invalid", is_active=True),
                Endpoint(name="inactive", url="https://b.invalid", is_active=False),
            ]
        )
        await db.commit()
    response = await client.get("/api/v1/endpoints", params={"skip": 1, "limit": 1})
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert len(response.json()["endpoints"]) == 1


@pytest.mark.asyncio
async def test_empty_database_has_zero_total(api_db):
    client, _, _ = api_db
    for active_only in ("true", "false"):
        response = await client.get("/api/v1/endpoints", params={"active_only": active_only})
        assert response.status_code == 200
        assert response.json() == {"endpoints": [], "total": 0}
