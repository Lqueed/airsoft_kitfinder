"""Общие фикстуры тестов.

`session` даёт async-сессию БД, обёрнутую во внешнюю транзакцию с откатом:
всё, что тест (и код под тестом) коммитит, откатывается после теста — БД чистая.
Требует поднятого PostgreSQL (см. docker-compose / локальный инстанс).
"""

from collections.abc import AsyncIterator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


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
