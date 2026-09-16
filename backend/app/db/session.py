"""Async engine, session factory, and schema creation.

``create_all`` is used instead of Alembic migrations. For a project whose
schema is defined once and shipped, a migration tool is ceremony — but it is
the first thing to add the moment this has real data to preserve, and
``ARCHITECTURE.md`` says so explicitly rather than leaving it as an accidental
omission.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db.models import Base

_is_sqlite = settings.database_url.startswith("sqlite")
_is_memory = ":memory:" in settings.database_url

engine = create_async_engine(
    settings.database_url,
    echo=settings.db_echo,
    future=True,
    # An in-memory SQLite database lives inside its connection. The default
    # pool hands out a fresh connection per checkout, so each one would see
    # an empty database. StaticPool pins a single shared connection, which is
    # what makes the test suite work against :memory:.
    **({"poolclass": StaticPool, "connect_args": {"check_same_thread": False}} if _is_memory else {}),
)

SessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep objects usable after commit, for responses
    autoflush=False,
)


if _is_sqlite and not _is_memory:

    @event.listens_for(engine.sync_engine, "connect")
    def _configure_sqlite(dbapi_connection, _record) -> None:  # type: ignore[no-untyped-def]
        """Apply the pragmas SQLite needs to behave under concurrent access.

        SQLite defaults are tuned for a single embedded writer. Two changes
        matter for a web app:

        * ``WAL`` lets readers proceed while a write is in flight. Without it
          the analytics query blocks every time a ticket is created, which is
          exactly the pattern this app has.
        * ``foreign_keys`` is OFF by default in SQLite — the ON DELETE CASCADE
          on overrides is silently ignored unless this is set per connection.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()


async def init_db() -> None:
    """Create any missing tables."""
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose_db() -> None:
    """Close the pool on shutdown."""
    await engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession]:
    """FastAPI dependency yielding a session that always closes."""
    async with SessionLocal() as session:
        yield session
