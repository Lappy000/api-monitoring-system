"""Real ASGI/SQLite endpoint contracts, without lifespan or external transport."""

import uuid
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.session import get_db
from app.models.endpoint import Endpoint


@pytest.fixture
async def api_db(monkeypatch):
    from app.main import app

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", poolclass=StaticPool)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async def database():
        async with sessions() as session:
            yield session

    monkeypatch.setitem(app.dependency_overrides, get_db, database)
    monkeypatch.setattr("app.api.endpoints.get_scheduler", lambda: None)
    transport = ASGITransport(app=app, client=(str(uuid.uuid4()), 123))
    try:
        async with AsyncClient(
            transport=transport, base_url="http://synthetic.invalid", trust_env=False
        ) as client:
            yield client, sessions, engine
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize("skip,limit", [(0, 1), (1, 1), (9, 1), (0, 0)])
async def test_active_total_uses_same_filter_before_pagination(api_db, skip, limit):
    client, sessions, engine = api_db
    async with sessions() as db:
        db.add_all(
            [
                Endpoint(name="active-a", url="https://a.invalid", is_active=True),
                Endpoint(name="inactive", url="https://b.invalid", is_active=False),
                Endpoint(name="active-c", url="https://c.invalid", is_active=True),
            ]
        )
        await db.commit()
    statements = []

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lower())

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    response = await client.get(
        "/api/v1/endpoints", params={"active_only": "true", "skip": skip, "limit": limit}
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["total"] == 2
    assert len(payload["endpoints"]) == (1 if skip < 2 and limit else 0)
    assert all(row["is_active"] for row in payload["endpoints"])
    assert len(statements) == 2
    assert any("count(" in sql and "where" in sql for sql in statements)


@pytest.mark.asyncio
async def test_crud_round_trip_and_empty_delete_body(api_db):
    client, sessions, _ = api_db
    payload = {
        "name": "synthetic",
        "url": "https://synthetic.invalid/health?q=1",
        "method": "POST",
        "headers": {"X-Test": "local"},
        "body": {"nested": [1, True, None]},
        "is_active": False,
    }
    created = await client.post("/api/v1/endpoints", json=payload)
    assert created.status_code == 201, created.text
    data = created.json()
    endpoint_id = data["id"]
    assert endpoint_id > 0
    assert {key: data[key] for key in payload} == payload
    assert data["interval"] == 60 and data["timeout"] == 5
    datetime.fromisoformat(data["created_at"])
    datetime.fromisoformat(data["updated_at"])
    uuid.UUID(created.headers["x-request-id"])
    async with sessions() as db:
        stored = await db.get(Endpoint, endpoint_id)
        assert stored.url == payload["url"]
        assert isinstance(stored.url, str)
        assert stored.body == payload["body"]
    read = await client.get(f"/api/v1/endpoints/{endpoint_id}")
    assert read.status_code == 200 and read.json() == data
    updated = await client.put(
        f"/api/v1/endpoints/{endpoint_id}",
        json={"url": "https://changed.invalid/path", "headers": None, "body": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["url"] == "https://changed.invalid/path"
    assert updated.json()["headers"] is None and updated.json()["body"] is None
    assert updated.json()["name"] == payload["name"]
    async with sessions() as db:
        stored = await db.get(Endpoint, endpoint_id)
        assert stored.url == "https://changed.invalid/path"
        assert stored.body is None and stored.headers is None
    deleted = await client.delete(f"/api/v1/endpoints/{endpoint_id}")
    assert deleted.status_code == 204, deleted.text
    assert deleted.content == b""
    missing = await client.get(f"/api/v1/endpoints/{endpoint_id}")
    assert missing.status_code == 404
    async with sessions() as db:
        assert (await db.execute(select(Endpoint))).scalars().all() == []
