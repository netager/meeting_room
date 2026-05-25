"""
Test fixtures.

Password hashing is mocked for speed (bcrypt rounds=12 takes ~0.3s per hash).
The mock uses a reversible prefix scheme: hash("foo") == "$test$foo".
Audit log writes (separate session) are mocked to avoid polluting the dev DB.
All DB changes go through a single connection with transaction rollback.
A NullPool engine is used per test to avoid asyncpg event-loop affinity issues.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import settings
from app.db import get_db
from app.main import app
from app.models import AdminAccount, Department, Employee


# ── Password mock ─────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_password_ops(monkeypatch):
    """Replace bcrypt with fast reversible hash for tests."""

    def fast_hash(password: str) -> str:
        return f"$test${password}"

    def fast_verify(plain: str, hashed: str) -> bool:
        return hashed == f"$test${plain}"

    monkeypatch.setattr("app.services.auth_service.hash_password", fast_hash)
    monkeypatch.setattr("app.services.auth_service.verify_password", fast_verify)
    monkeypatch.setattr("app.routers.auth.hash_password", fast_hash)


# ── Audit log mock ────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def mock_audit_log(monkeypatch):
    """Suppress audit log DB writes in tests."""

    async def noop(*args, **kwargs):
        pass

    monkeypatch.setattr("app.services.auth_service._log_audit", noop)


# ── DB session (transactional rollback, NullPool) ─────────────────────────────


@pytest_asyncio.fixture
async def db():
    """
    Fresh connection per test using NullPool — avoids asyncpg event-loop affinity.
    create_savepoint mode: session.commit() releases savepoints instead of
    committing the outer transaction, so all changes are rolled back at teardown.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool, echo=False)
    try:
        async with engine.connect() as connection:
            await connection.begin()
            session = AsyncSession(
                bind=connection,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            )

            # Common test data: a department (required by Employee FK)
            dept = Department(code="TESTDEPT", name="테스트부서")
            session.add(dept)
            await session.flush()

            yield session

            await session.close()
            await connection.rollback()
    finally:
        await engine.dispose()


# ── Test data fixtures ────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def test_admin(db: AsyncSession) -> AdminAccount:
    """Admin account in test transaction (is_initial_password=False)."""
    admin = AdminAccount(
        username="admin",
        password_hash="$test$admin123",
        is_initial_password=False,
    )
    db.add(admin)
    await db.flush()
    return admin


@pytest_asyncio.fixture
async def test_employee(db: AsyncSession) -> Employee:
    """Active employee with is_initial_password=True."""
    emp = Employee(
        emp_no="T00001",
        name="테스트직원",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=True,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest_asyncio.fixture
async def active_employee(db: AsyncSession) -> Employee:
    """Active employee with is_initial_password=False."""
    emp = Employee(
        emp_no="T00002",
        name="활성직원",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="ACTIVE",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


@pytest_asyncio.fixture
async def retired_employee(db: AsyncSession) -> Employee:
    """Retired employee."""
    emp = Employee(
        emp_no="T00003",
        name="퇴직직원",
        dept_code="TESTDEPT",
        password_hash="$test$Password1",
        status="RETIRED",
        is_initial_password=False,
        login_fail_count=0,
    )
    db.add(emp)
    await db.flush()
    return emp


# ── HTTP client ───────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client(db: AsyncSession, test_admin: AdminAccount):
    """
    AsyncClient with DB session overridden and startup suppressed.
    The test_admin fixture is included so admin always exists in test transaction.
    """
    from unittest.mock import AsyncMock, patch

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    with patch(
        "app.repositories.auth_repo.create_admin_account_if_not_exists",
        new=AsyncMock(),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c

    app.dependency_overrides.clear()
