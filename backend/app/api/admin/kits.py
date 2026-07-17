"""Админ-API китов: CRUD кита и позиций, публикация, предпросмотр flexible-позиции."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_admin
from app.db import SessionDep
from app.models.catalog import Kit, KitItem
from app.models.enums import KitStatus
from app.schemas.kits import (
    FlexiblePreviewOut,
    FlexibleVariantOut,
    KitCreate,
    KitItemCreate,
    KitItemUpdate,
    KitListItemOut,
    KitOut,
    KitPricingOut,
    KitUpdate,
)
from app.services.kit_pricing import flexible_variants, price_kit, product_min_price
from app.services.slugs import slugify

router = APIRouter(prefix="/api/admin", tags=["admin-kits"], dependencies=[Depends(require_admin)])


async def _get_kit(session: AsyncSession, kit_id: int) -> Kit:
    """Загружает кит с позициями или отдаёт 404."""
    kit = await session.scalar(select(Kit).where(Kit.id == kit_id).options(selectinload(Kit.items)))
    if kit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кит не найден")
    return kit


async def _get_item(session: AsyncSession, item_id: int) -> KitItem:
    """Загружает позицию кита или отдаёт 404."""
    item = await session.get(KitItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Позиция не найдена")
    return item


async def _unique_slug(session: AsyncSession, name: str) -> str:
    """Уникальный slug кита: транслит имени + числовой суффикс при коллизии."""
    base = slugify(name)
    slug = base
    n = 2
    while await session.scalar(select(Kit.id).where(Kit.slug == slug)) is not None:
        slug = f"{base}-{n}"
        n += 1
    return slug


async def _kit_out(session: AsyncSession, kit: Kit) -> KitOut:
    """Собирает KitOut с посчитанной вилкой цены."""
    pricing = await price_kit(session, list(kit.items))
    return KitOut(
        id=kit.id,
        slug=kit.slug,
        name=kit.name,
        description=kit.description,
        role=kit.role,
        drive_type=kit.drive_type,
        experience_level=kit.experience_level,
        status=kit.status,
        image_url=kit.image_url,
        items=kit.items,
        pricing=KitPricingOut.model_validate(pricing),
    )


@router.get("/kits", response_model=list[KitListItemOut])
async def list_kits(session: SessionDep) -> list[KitListItemOut]:
    """Список китов с вилкой цены (без позиций)."""
    kits = (
        await session.scalars(
            select(Kit).order_by(Kit.created_at.desc()).options(selectinload(Kit.items))
        )
    ).all()
    result: list[KitListItemOut] = []
    for kit in kits:
        pricing = await price_kit(session, list(kit.items))
        result.append(
            KitListItemOut(
                id=kit.id,
                slug=kit.slug,
                name=kit.name,
                role=kit.role,
                drive_type=kit.drive_type,
                experience_level=kit.experience_level,
                status=kit.status,
                image_url=kit.image_url,
                pricing=KitPricingOut.model_validate(pricing),
            )
        )
    return result


@router.post("/kits", response_model=KitOut, status_code=status.HTTP_201_CREATED)
async def create_kit(body: KitCreate, session: SessionDep) -> KitOut:
    """Создаёт кит-черновик."""
    kit = Kit(
        slug=await _unique_slug(session, body.name),
        name=body.name,
        description=body.description,
        role=body.role,
        drive_type=body.drive_type,
        experience_level=body.experience_level,
        image_url=body.image_url,
        status=KitStatus.DRAFT,
    )
    session.add(kit)
    await session.flush()
    await session.refresh(kit, attribute_names=["items"])
    await session.commit()
    return await _kit_out(session, kit)


@router.get("/kits/{kit_id}", response_model=KitOut)
async def get_kit(kit_id: int, session: SessionDep) -> KitOut:
    """Кит с позициями и вилкой цены."""
    return await _kit_out(session, await _get_kit(session, kit_id))


@router.patch("/kits/{kit_id}", response_model=KitOut)
async def update_kit(kit_id: int, body: KitUpdate, session: SessionDep) -> KitOut:
    """Обновляет поля кита (частично)."""
    kit = await _get_kit(session, kit_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(kit, field, value)
    await session.commit()
    return await _kit_out(session, kit)


@router.delete("/kits/{kit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_kit(kit_id: int, session: SessionDep) -> Response:
    """Удаляет кит вместе с позициями (cascade)."""
    kit = await _get_kit(session, kit_id)
    await session.delete(kit)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/kits/{kit_id}/publish", response_model=KitOut)
async def publish_kit(kit_id: int, session: SessionDep) -> KitOut:
    """Публикует кит. Неполный кит (нет цены у обязательной позиции) публиковать нельзя."""
    kit = await _get_kit(session, kit_id)
    pricing = await price_kit(session, list(kit.items))
    if not pricing.complete:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Кит неполный: у обязательной позиции нет доступной цены",
        )
    kit.status = KitStatus.PUBLISHED
    await session.commit()
    return await _kit_out(session, kit)


@router.post("/kits/{kit_id}/unpublish", response_model=KitOut)
async def unpublish_kit(kit_id: int, session: SessionDep) -> KitOut:
    """Снимает кит с публикации (возврат в черновик)."""
    kit = await _get_kit(session, kit_id)
    kit.status = KitStatus.DRAFT
    await session.commit()
    return await _kit_out(session, kit)


@router.post("/kits/{kit_id}/items", response_model=KitOut, status_code=status.HTTP_201_CREATED)
async def add_item(kit_id: int, body: KitItemCreate, session: SessionDep) -> KitOut:
    """Добавляет позицию в кит."""
    await _get_kit(session, kit_id)  # 404, если кита нет
    session.add(
        KitItem(
            kit_id=kit_id,
            item_type=body.item_type,
            title=body.title,
            is_required=body.is_required,
            sort_order=body.sort_order,
            product_id=body.product_id,
            category_id=body.category_id,
            max_price=body.max_price,
            attr_filters=body.attr_filters,
        )
    )
    await session.commit()
    return await _kit_out(session, await _get_kit(session, kit_id))


@router.patch("/items/{item_id}", response_model=KitOut)
async def update_item(item_id: int, body: KitItemUpdate, session: SessionDep) -> KitOut:
    """Обновляет позицию кита (частично)."""
    item = await _get_item(session, item_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    await session.commit()
    return await _kit_out(session, await _get_kit(session, item.kit_id))


@router.delete("/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(item_id: int, session: SessionDep) -> Response:
    """Удаляет позицию кита."""
    item = await _get_item(session, item_id)
    await session.delete(item)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/kit-items/{item_id}/preview", response_model=FlexiblePreviewOut)
async def preview_item(item_id: int, session: SessionDep) -> FlexiblePreviewOut:
    """Предпросмотр вариантов flexible-позиции с ценами."""
    item = await _get_item(session, item_id)
    variants = await flexible_variants(session, item)
    out: list[FlexibleVariantOut] = []
    for product in variants:
        out.append(
            FlexibleVariantOut(
                product_id=product.id,
                name=product.name,
                brand=product.brand,
                min_price=await product_min_price(session, product.id),
            )
        )
    out.sort(key=lambda v: (v.min_price is None, v.min_price or 0))
    return FlexiblePreviewOut(item_id=item.id, variants=out)
