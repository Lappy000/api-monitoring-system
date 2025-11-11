"""Database session management with async support."""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool, AsyncAdaptedQueuePool

# Get database URL from environment or use default SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/api_monitor.db")

# Determine pool class based on database type
if "sqlite" in DATABASE_URL:
    # For SQLite in async applications, use proper connection pooling
    # StaticPool creates a bottleneck - all requests serialize on one connection
    # Use NullPool for SQLite which creates connections on demand
    from sqlalchemy.pool import NullPool
    pool_class = NullPool
    pool_kwargs = {}
else:
    # For PostgreSQL/MySQL, use proper connection pooling
    pool_class = AsyncAdaptedQueuePool
    pool_kwargs = {
        "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
        "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10")),
        "pool_pre_ping": True,
        "pool_recycle": 3600,  # Recycle connections after 1 hour
    }

# Create async engine
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() == "true",
    poolclass=pool_class,
    **pool_kwargs
)

# Create async session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting async database sessions.
    
    This function provides a clean database session that automatically
    handles commit/rollback and properly closes connections.
    
    Yields:
        AsyncSession: Database session
        
    Example:
        ```python
        from fastapi import Depends
        from sqlalchemy import select
        
        async def some_endpoint(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Endpoint))
            return result.scalars().all()
        ```
    """
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        # No need to explicitly close - context manager handles it


# For backward compatibility and direct usage (not recommended)
# Use get_db() dependency in FastAPI endpoints instead
async def get_db_direct() -> AsyncGenerator[AsyncSession, None]:
    """Direct database session (use get_db() with Depends() instead)."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise