"""Асинхронное подключение к БД и базовый класс моделей SQLAlchemy."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


class Base(DeclarativeBase):
    """Базовый класс для всех ORM-моделей."""


engine = create_async_engine(settings.database_url, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость: сессия БД на время запроса."""
    async with SessionLocal() as session:
        yield session


# Готовая аннотированная зависимость сессии для сигнатур эндпоинтов
# (паттерн FastAPI Annotated — без вызова в дефолте аргумента).
SessionDep = Annotated[AsyncSession, Depends(get_session)]
