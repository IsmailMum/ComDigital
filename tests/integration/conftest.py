import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    async_sessionmaker,
    AsyncSession,
)
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel

from app.main import app
from app.api.dependencies import get_db, get_current_user
from app.models import User


# ── Async SQLite engine (one in-memory DB per test function) ────────


@pytest_asyncio.fixture
async def engine():
    _engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite does not support FOR UPDATE – silently strip it.
    @event.listens_for(_engine.sync_engine, "before_cursor_execute", retval=True)
    def _strip_for_update(conn, cursor, stmt, params, context, executemany):
        return stmt.replace(" FOR UPDATE", ""), params

    async with _engine.begin() as conn:
        await conn.execute(text("PRAGMA foreign_keys = ON"))
        await conn.run_sync(SQLModel.metadata.create_all)

    yield _engine
    await _engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Raw session for inserting test data directly."""
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with factory() as session:
        yield session


# ── Persist test users in the DB ────────────────────────────────────


@pytest_asyncio.fixture
async def registered_user(db_session, test_user) -> User:
    db_session.add(test_user)
    await db_session.commit()
    return test_user


@pytest_asyncio.fixture
async def registered_superuser(db_session, test_superuser) -> User:
    db_session.add(test_superuser)
    await db_session.commit()
    return test_superuser


@pytest_asyncio.fixture
async def registered_other_user(db_session, other_user) -> User:
    db_session.add(other_user)
    await db_session.commit()
    return other_user


# ── HTTP clients with real DB sessions ──────────────────────────────


@pytest_asyncio.fixture
async def client(engine, registered_user):
    """Client authenticated as a regular user backed by a real SQLite DB."""
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: registered_user

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def superuser_client(engine, registered_user, registered_superuser):
    """Client authenticated as superuser.

    Also depends on ``registered_user`` so regular-user items can exist.
    """
    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def _get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: registered_superuser

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
