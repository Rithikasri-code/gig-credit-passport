"""
Shared test fixtures.

CRITICAL: the DATABASE_URL override below must happen before any `app.*`
module is imported, since app.core.config.Settings reads the environment
at import time. This is what makes the entire test suite run against
gigpassport_test instead of your real dev database — nothing here can
accidentally touch real data.
"""
import os

os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/gigpassport_test"
os.environ["DEBUG"] = "true"  # needed so OTP requests return debug_otp for tests to read
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.db import session as db_session_module
from app.db.session import Base


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_test_database():
    """
    Creates all tables once before the test session, drops them after.

    IMPORTANT: the engine/session-maker created at import time in
    app/db/session.py is bound to whatever event loop existed when the
    module was first imported (e.g. during pytest collection), which is
    NOT the same loop pytest-asyncio's session-scoped event loop fixture
    creates. Reusing the import-time engine causes 'attached to a
    different loop' errors the moment any async DB call happens. The fix
    is to dispose that engine and recreate it here, inside a fixture that
    genuinely runs inside the correct session loop.
    """
    await db_session_module.engine.dispose()

    new_engine = create_async_engine(db_session_module.settings.DATABASE_URL, echo=False, future=True)
    new_session_local = async_sessionmaker(bind=new_engine, class_=AsyncSession, expire_on_commit=False)

    # Reassigning these module attributes (rather than local variables) is
    # what makes every `Depends(get_db)` call site pick up the corrected
    # engine — get_db() looks up AsyncSessionLocal from the module's
    # global namespace at call time, not at import time.
    db_session_module.engine = new_engine
    db_session_module.AsyncSessionLocal = new_session_local

    async with new_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with new_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await new_engine.dispose()


@pytest_asyncio.fixture(autouse=True)
async def clean_tables():
    """
    Truncates every table between tests so they don't leak state into
    each other — each test starts from a genuinely empty database, not
    just 'probably fine because it ran first'.
    """
    yield
    async with db_session_module.AsyncSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            await session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        await session.commit()


@pytest_asyncio.fixture
async def client():
    """An httpx client that talks directly to the FastAPI app in-process — no real network hop."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def register_and_login(client: AsyncClient, phone_number: str, full_name: str = "Test User") -> dict:
    """
    Shared helper: most tests need an authenticated user before testing
    anything else. Returns {"token": ..., "user_id": ...}.
    """
    otp_resp = await client.post("/api/v1/auth/otp/request", json={"phone_number": phone_number})
    otp = otp_resp.json()["debug_otp"]

    verify_resp = await client.post(
        "/api/v1/auth/otp/verify",
        json={"phone_number": phone_number, "otp": otp, "full_name": full_name},
    )
    data = verify_resp.json()
    return {"token": data["access_token"], "user_id": data["user_id"]}


async def link_and_sync_account(client: AsyncClient, token: str) -> str:
    """Shared helper: link a mock account and sync it, returning the consent_id."""
    headers = {"Authorization": f"Bearer {token}"}
    consent_resp = await client.post(
        "/api/v1/consent/initiate", json={"purpose": "test"}, headers=headers
    )
    consent_id = consent_resp.json()["id"]
    await client.post(f"/api/v1/accounts/sync/{consent_id}", headers=headers)
    return consent_id
