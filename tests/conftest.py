"""Pytest configuration and fixtures."""

import pytest
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import FastAPI

from app.database.base import Base
from app.models.endpoint import Endpoint
from app.models.check_result import CheckResult
from app.config import Config, DatabaseConfig
from app.database.session import get_db


# Test database URL
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

# Global test engine and session maker
_test_engine = None
_test_session_maker = None


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def db_engine():
    """Create test database engine for session."""
    global _test_engine
    
    # Import all models to register with Base.metadata
    from app.models.endpoint import Endpoint
    from app.models.check_result import CheckResult
    from app.models.notification_log import NotificationLog
    
    _test_engine = create_async_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # Create all tables
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield _test_engine
    
    # Cleanup
    await _test_engine.dispose()


@pytest.fixture(scope="session")
def session_maker(db_engine):
    """Create session maker for tests."""
    global _test_session_maker
    _test_session_maker = async_sessionmaker(
        db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    return _test_session_maker


@pytest.fixture(scope="function")
async def db_session(session_maker) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session with automatic cleanup."""
    async with session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise
        finally:
            # Clean up all data after each test
            try:
                from app.models.notification_log import NotificationLog
                from app.models.check_result import CheckResult
                from app.models.endpoint import Endpoint
                
                # Delete in correct order due to foreign keys
                await session.execute(NotificationLog.__table__.delete())
                await session.execute(CheckResult.__table__.delete())
                await session.execute(Endpoint.__table__.delete())
                await session.commit()
            except Exception:
                await session.rollback()




@pytest.fixture(scope="function")
def test_app(session_maker):
    """Create test FastAPI app with overridden dependencies."""
    from app.main import app
    
    # Create dependency override closure that captures session_maker
    async def get_test_db():
        async with session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
    
    # Override database dependency
    app.dependency_overrides[get_db] = get_test_db
    
    yield app
    
    # Clean up overrides
    app.dependency_overrides.clear()


@pytest.fixture
async def sample_endpoint(db_session: AsyncSession) -> Endpoint:
    """Create sample endpoint for testing."""
    endpoint = Endpoint(
        name="Test Endpoint",
        url="https://httpbin.org/status/200",
        method="GET",
        interval=60,
        timeout=5,
        expected_status=200,
        is_active=True
    )
    
    db_session.add(endpoint)
    await db_session.commit()
    await db_session.refresh(endpoint)
    
    return endpoint


@pytest.fixture
def test_config() -> Config:
    """Create test configuration."""
    return Config(
        database=DatabaseConfig(
            type="sqlite",
            url=TEST_DATABASE_URL
        )
    )