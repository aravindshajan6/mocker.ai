"""Test fixtures.

Tests run inside the backend container against the live Postgres service; each test gets a
fresh user so state never leaks between tests. Run with:
    docker compose exec backend python -m pytest tests -q
"""
import os
import random
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE = os.environ.get("TEST_BASE_URL", "http://localhost:8000")


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE


@pytest.fixture
def client(base_url):
    with httpx.Client(base_url=base_url, timeout=60) as c:
        yield c


@pytest.fixture
def user(client):
    """A freshly registered, signed-in user, removed again when the test ends.

    Without the teardown every run leaves another "Pytest User" on the leaderboard, which real
    users then see.
    """
    email = f"pytest{random.randint(1, 10**9)}@example.com"
    r = client.post("/api/auth/register", json={"name": "Pytest User", "email": email, "password": "secret123"})
    assert r.status_code == 200, r.text
    data = r.json()
    yield data
    _purge(data["id"])


def _purge(user_id: str) -> None:
    """Delete a test user directly; cascades clear their attempts, sessions, stats and cards."""
    import asyncio

    async def go():
        from sqlalchemy import delete
        from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
        from sqlalchemy.pool import NullPool

        from app.config import settings
        from app.models import User

        engine = create_async_engine(settings.database_url, poolclass=NullPool)
        try:
            async with async_sessionmaker(engine, expire_on_commit=False)() as db:
                await db.execute(delete(User).where(User.id == user_id))
                await db.commit()
        finally:
            await engine.dispose()

    try:
        asyncio.run(go())
    except Exception:  # noqa: BLE001 - cleanup must never fail a passing test
        pass


@pytest.fixture
async def db_session():
    """A real database session for tests that exercise service-layer code directly.

    Builds its own engine with no pooling: the app's shared engine is bound to the running
    server's event loop, and reusing it from a test loop raises "Event loop is closed".
    """
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.config import settings

    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()
