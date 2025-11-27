"""Database connection and session management for BIMCalc.

Provides async SQLAlchemy session management with connection pooling.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from bimcalc.config import get_config
from bimcalc.db.models import Base

# Global engine instance
_engine: AsyncEngine | None = None
_session_factory: sessionmaker | None = None


def get_engine() -> AsyncEngine:
    """Get or create singleton async engine.

    Returns:
        AsyncEngine: SQLAlchemy async engine

    Raises:
        RuntimeError: If database URL is not configured
    """
    global _engine

    if _engine is None:
        config = get_config()
        db_config = config.db

        # Build engine kwargs
        engine_kwargs = {"echo": db_config.echo}

        # SQLite doesn't support connection pooling parameters
        if "sqlite" not in db_config.url.lower():
            engine_kwargs.update({
                "pool_size": db_config.pool_size,
                "max_overflow": db_config.pool_max_overflow,
                "pool_timeout": db_config.pool_timeout,
                "pool_pre_ping": True,  # Verify connections before using
                "pool_recycle": 3600,  # Recycle connections after 1 hour
            })

        # Create async engine
        _engine = create_async_engine(db_config.url, **engine_kwargs)

        # Register SQLite functions
        if "sqlite" in db_config.url.lower():
            from sqlalchemy import event
            from datetime import datetime
            
            @event.listens_for(_engine.sync_engine, "connect")
            def connect(dbapi_connection, connection_record):
                try:
                    dbapi_connection.create_function("now", 0, lambda: datetime.utcnow().isoformat(" "))
                except Exception:
                    pass

    return _engine


def get_session_factory() -> sessionmaker:
    """Get or create session factory.

    Returns:
        sessionmaker: Session factory for creating AsyncSession instances
    """
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,  # Don't expire objects after commit
        )

    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session (context manager).

    Usage:
        async with get_session() as session:
            result = await session.execute(query)
            await session.commit()

    Yields:
        AsyncSession: SQLAlchemy async session

    Raises:
        SQLAlchemyError: If database operation fails
    """
    session_factory = get_session_factory()
    session = session_factory()

    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def init_db() -> None:
    """Initialize database (create all tables).

    Note: For production, use Alembic migrations instead.
    This is a convenience function for development/testing.

    Raises:
        SQLAlchemyError: If table creation fails
    """
    engine = get_engine()

    async with engine.begin() as conn:
        # Create all tables defined in Base metadata
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Close database engine and dispose connections.

    Call this on application shutdown.
    """
    global _engine, _session_factory

    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
