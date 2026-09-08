"""
ARIA / SAKHI — Database
========================
Async SQLAlchemy engine and session factory (lazy-initialized).

The engine is NOT created at import time. It is created on first use via
get_engine(). This allows tests to set DATABASE_URL=sqlite+aiosqlite:///:memory:
before the engine is instantiated, without triggering asyncpg imports.

Usage in route handlers:
    async def route(db: AsyncSession = Depends(get_db)): ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import TypeDecorator, Uuid
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared declarative base for all SQLAlchemy models."""

    pass


class GUID(TypeDecorator[Any]):
    """Platform-independent GUID type.
    Uses native UUID on PostgreSQL, and CHAR(32) on SQLite,
    safely handling both uuid.UUID and string representations in queries.
    """

    impl = Uuid
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            import uuid as _uuid

            try:
                return _uuid.UUID(value)
            except ValueError:
                return value
        return value


# ── Lazy singletons ────────────────────────────────────────────────────────────
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None  # type: ignore[type-arg]


def get_engine() -> AsyncEngine:
    """Return the shared async engine, creating it on first call."""
    global _engine
    if _engine is None:
        from app.config import get_settings

        settings = get_settings()
        # SQLite (used in tests) does not support pool_size / max_overflow
        is_sqlite = settings.DATABASE_URL.startswith("sqlite")
        kwargs: dict[str, Any] = {"echo": settings.DEBUG}
        if not is_sqlite:
            kwargs.update(pool_pre_ping=True, pool_size=10, max_overflow=20)
        _engine = create_async_engine(settings.DATABASE_URL, **kwargs)
    return _engine


def get_session_factory() -> async_sessionmaker:  # type: ignore[type-arg]
    """Return the session factory, creating it on first call."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
    return _session_factory


def reset_engine() -> None:
    """Reset engine and session factory. Used in tests to switch databases."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


def __getattr__(name: str) -> Any:
    if name == "engine":
        return get_engine()
    if name == "AsyncSessionLocal":
        return get_session_factory()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
