"""Общие фикстуры тестов.

`session` даёт async-сессию БД, обёрнутую во внешнюю транзакцию с откатом:
всё, что тест (и код под тестом) коммитит, откатывается после теста — БД чистая.
Требует поднятого PostgreSQL (см. docker-compose / локальный инстанс).

`client`/`admin_client` — httpx.AsyncClient поверх ASGI-приложения с подменённой
на тестовую `session` зависимостью БД (тот же event loop, иначе asyncpg падает на
разных loop'ах). `admin_client` дополнительно залогинен админской cookie.
"""

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import hash_password
from app.config import settings
from app.db import get_session
from app.main import app

ADMIN_PASSWORD = "test-pass"


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(settings.database_url)
    connection = await engine.connect()
    transaction = await connection.begin()
    maker = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    db_session = maker()
    try:
        yield db_session
    finally:
        await db_session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент к приложению; get_session подменён на тестовую транзакцию."""
    monkeypatch.setattr(settings, "admin_password_hash", hash_password(ADMIN_PASSWORD))
    monkeypatch.setattr(settings, "secret_key", "test-secret")
    monkeypatch.setattr(settings, "login_fail_delay_seconds", 0.0)
    monkeypatch.setattr(settings, "cookie_secure", False)  # cookie ходит по http в тесте

    async def _override() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(client: AsyncClient) -> AsyncClient:
    """Клиент с активной админской сессией (после успешного логина)."""
    response = await client.post("/api/admin/login", json={"password": ADMIN_PASSWORD})
    assert response.status_code == 200
    return client
