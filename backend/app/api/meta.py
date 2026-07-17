"""Публичный справочник для форм и фильтров: роли, типы приводов, категории."""

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.db import SessionDep
from app.models.catalog import Category
from app.models.enums import DriveType, ExperienceLevel, Role

router = APIRouter(prefix="/api", tags=["meta"])


class CategoryOut(BaseModel):
    """Категория нашей таксономии."""

    model_config = {"from_attributes": True}

    id: int
    slug: str
    name: str


class MetaOut(BaseModel):
    """Справочники для селектов и фильтров."""

    roles: list[str]
    drive_types: list[str]
    experience_levels: list[str]
    categories: list[CategoryOut]


@router.get("/meta", response_model=MetaOut)
async def get_meta(session: SessionDep) -> MetaOut:
    """Отдаёт значения перечислений и список категорий."""
    categories = (await session.scalars(select(Category).order_by(Category.name))).all()
    return MetaOut(
        roles=[r.value for r in Role],
        drive_types=[d.value for d in DriveType],
        experience_levels=[e.value for e in ExperienceLevel],
        categories=[CategoryOut.model_validate(c) for c in categories],
    )
