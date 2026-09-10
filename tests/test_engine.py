"""HealthChecker contracts exercised through a local aiohttp-shaped transport."""

import asyncio
from datetime import datetime
from unittest.mock import Mock

import aiohttp
import pytest
from sqlalchemy import select

from app.core import circuit_breaker
from app.core.health_checker import HealthChecker
from app.models.check_result import CheckResult
from app.models.endpoint import Endpoint
from tests.test_endpoint_asgi import api_db as api_db


class LocalResponse:
    def __init__(self, status=200, error=None):
        self.status = status
        self.error = error
        self.read_count = 0
        self.exited = False

    async def __aenter__(self):
        if self.error:
            raise self.error
        return self

    async def __aexit__(self, *args):
        self.exited = True

    async def read(self):
        self.read_count += 1
        await asyncio.sleep(0)
        return b"synthetic response"


class LocalSession:
    def __init__(self, response):
        self.response = response
        self.calls = []
        self.closed = False

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    async def close(self):
        self.closed = True


@pytest.fixture(autouse=True)
def local_transport_only(monkeypatch):
    monkeypatch.setattr(
        circuit_breaker, "circuit_breaker_registry", circuit_breaker.CircuitBreakerRegistry()
    )
    factory = Mock(side_effect=AssertionError("Unexpected real HTTP session"))
    monkeypatch.setattr("app.core.health_checker.aiohttp.ClientSession", factory)
    yield
    factory.assert_not_called()


@pytest.fixture
def endpoint():
    return Endpoint(
        id=1,
        name="local-check",
        url="https://synthetic.invalid/health",
        method="GET",
        timeout=3,
        expected_status=200,
        headers={"X-Test": "local"},
        body={"value": 1},
    )


def test_checker_defaults_are_lazy():
    checker = HealthChecker()
    assert checker.session is None
    assert checker.max_concurrent == 20
    assert checker.default_timeout == 5


@pytest.mark.asyncio
async def test_session_lifecycle_is_idempotent(monkeypatch):
    session = LocalSession(LocalResponse())
    factory = Mock(return_value=session)
    connector = Mock(return_value=object())
    monkeypatch.setattr("app.core.health_checker.aiohttp.ClientSession", factory)
    monkeypatch.setattr("app.core.health_checker.aiohttp.TCPConnector", connector)
    checker = HealthChecker(max_concurrent=7, default_timeout=4)
    async with checker as opened:
        assert opened is checker and checker.session is session
        await checker.start()
        factory.assert_called_once()
        assert factory.call_args.kwargs["timeout"].total == 4
        connector.assert_called_once_with(limit=7)
    assert session.closed and checker.session is None
    await checker.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,expected,success", [(200, 200, True), (201, 201, True), (503, 200, False)]
)
async def test_result_preserves_http_status_and_response_body(endpoint, status, expected, success):
    endpoint.expected_status = expected
    response = LocalResponse(status)
    checker = HealthChecker()
    checker.session = LocalSession(response)
    result = await checker.check_endpoint(endpoint, use_retry=False)
    assert result.success is success
    assert result.status_code == status
    assert result.response_time >= 0
    assert isinstance(result.checked_at, datetime)
    assert response.read_count == 1 and response.exited
    assert len(checker.session.calls) == 1
    assert result.error_message == (
        None if success else f"Expected status {expected}, got {status}"
    )
    await checker.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,has_body",
    [("get", False), ("DELETE", False), ("post", True), ("PUT", True), ("PATCH", True)],
)
async def test_request_arguments_preserve_endpoint_contract(endpoint, method, has_body):
    endpoint.method = method
    checker = HealthChecker()
    session = LocalSession(LocalResponse())
    checker.session = session
    result = await checker.check_endpoint(endpoint, use_retry=False)
    assert result.success
    assert len(session.calls) == 1
    request = session.calls[0]
    assert request["method"] == method.upper()
    assert request["url"] == endpoint.url
    assert request["headers"] == endpoint.headers
    assert request["timeout"].total == endpoint.timeout
    assert ("json" in request) is has_body
    if has_body:
        assert request["json"] == endpoint.body
    await checker.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error,message",
    [
        (asyncio.TimeoutError(), "Request timed out after 3s"),
        (aiohttp.ClientError("local transport failure"), "Client error: local transport failure"),
        (ValueError("local invalid response"), "Unexpected error: local invalid response"),
    ],
)
async def test_transport_failures_are_structured_results(endpoint, error, message):
    checker = HealthChecker()
    checker.session = LocalSession(LocalResponse(error=error))
    result = await checker.check_endpoint(endpoint, use_retry=False)
    assert result.success is False and result.status_code is None
    assert result.error_message == message
    assert result.response_time >= 0
    assert len(checker.session.calls) == 1
    await checker.close()


@pytest.mark.asyncio
async def test_check_and_save_persists_real_transport_result(api_db):
    _, sessions, _ = api_db
    checker = HealthChecker()
    checker.session = LocalSession(LocalResponse(503))
    async with sessions() as db:
        endpoint = Endpoint(name="saved-local", url="https://local.invalid", is_active=False)
        db.add(endpoint)
        await db.commit()
        result = await checker.check_and_save(endpoint, db)
        result_id, endpoint_id = result.id, endpoint.id
    async with sessions() as db:
        saved = (await db.execute(select(CheckResult))).scalar_one()
        assert saved.id == result_id and saved.endpoint_id == endpoint_id
        assert saved.status_code == 503 and saved.success is False
        assert saved.error_message == "Expected status 200, got 503"
        assert saved.response_time >= 0 and isinstance(saved.checked_at, datetime)
    await checker.close()
