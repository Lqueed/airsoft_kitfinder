"""Публичная витрина: каталог опубликованных китов и деталка кита."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import SessionDep
from app.models.catalog import Kit, KitItem
from app.models.enums import KitItemType, KitStatus
from app.schemas.catalog import ShopBrief
from app.schemas.public import (
    KitCardOut,
    KitCatalogOut,
    KitDetailItemOut,
    KitDetailOut,
    OfferView,
    ProductBrief,
    VariantView,
)
from app.services.kit_pricing import (
    KitPricing,
    flexible_variants,
    price_kit,
    product_min_price,
    product_offers,
)

router = APIRouter(prefix="/api", tags=["public"])

PAGE_SIZE = 12


def _card(kit: Kit, pricing: KitPricing) -> KitCardOut:
    """Карточка кита для каталога."""
    return KitCardOut(
        id=kit.id,
        slug=kit.slug,
        name=kit.name,
        role=kit.role,
        drive_type=kit.drive_type,
        experience_level=kit.experience_level,
        image_url=kit.image_url,
        price_min=pricing.price_min,
        price_max=pricing.price_max,
        complete=pricing.complete,
    )


def _in_budget(
    pricing: KitPricing, budget_min: Decimal | None, budget_max: Decimal | None
) -> bool:
    """Пересечение вилки кита с бюджетом: price_min ≤ budget_max И price_max ≥ budget_min."""
    if budget_min is None and budget_max is None:
        return True
    if pricing.price_min is None or pricing.price_max is None:
        return False  # неполный кит нельзя разместить в бюджет
    if budget_max is not None and pricing.price_min > budget_max:
        return False
    if budget_min is not None and pricing.price_max < budget_min:
        return False
    return True


@router.get("/kits", response_model=KitCatalogOut)
async def list_kits(
    session: SessionDep,
    role: str | None = None,
    drive_type: str | None = None,
    budget_min: Decimal | None = None,
    budget_max: Decimal | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
) -> KitCatalogOut:
    """Каталог опубликованных китов с фильтрами и пагинацией."""
    stmt = (
        select(Kit)
        .where(Kit.status == KitStatus.PUBLISHED)
        .order_by(Kit.created_at.desc())
        .options(selectinload(Kit.items))
    )
    if role:
        stmt = stmt.where(Kit.role == role)
    if drive_type:
        stmt = stmt.where(Kit.drive_type == drive_type)

    cards: list[KitCardOut] = []
    for kit in (await session.scalars(stmt)).all():
        pricing = await price_kit(session, list(kit.items))
        if _in_budget(pricing, budget_min, budget_max):
            cards.append(_card(kit, pricing))

    total = len(cards)
    start = (page - 1) * PAGE_SIZE
    return KitCatalogOut(
        items=cards[start : start + PAGE_SIZE], total=total, page=page, page_size=PAGE_SIZE
    )


async def _offer_views(session: SessionDep, product_id: int) -> list[OfferView]:
    """Офферы товара по магазинам (для кнопки «Купить»)."""
    return [
        OfferView(
            shop=ShopBrief.model_validate(offer.shop),
            price=offer.price,
            in_stock=offer.in_stock,
            url=offer.url,
        )
        for offer in await product_offers(session, product_id)
    ]


async def _detail_item(session: SessionDep, item: KitItem, pricing: KitPricing) -> KitDetailItemOut:
    """Собирает позицию деталки: fixed → товар+офферы, flexible → варианты."""
    item_pricing = next((p for p in pricing.items if p.item_id == item.id), None)
    out = KitDetailItemOut(
        id=item.id,
        title=item.title,
        item_type=item.item_type,
        is_required=item.is_required,
        sort_order=item.sort_order,
        min_price=item_pricing.min_price if item_pricing else None,
        max_price=item_pricing.max_price if item_pricing else None,
    )
    if item.item_type is KitItemType.FIXED and item.product is not None:
        out.product = ProductBrief.model_validate(item.product)
        out.offers = await _offer_views(session, item.product.id)
    elif item.item_type is KitItemType.FLEXIBLE:
        variants: list[VariantView] = []
        for product in await flexible_variants(session, item):
            variants.append(
                VariantView(
                    product=ProductBrief.model_validate(product),
                    min_price=await product_min_price(session, product.id),
                    offers=await _offer_views(session, product.id),
                )
            )
        variants.sort(key=lambda v: (v.min_price is None, v.min_price or 0))
        out.variants = variants
    return out


@router.get("/kits/{slug}", response_model=KitDetailOut)
async def get_kit(slug: str, session: SessionDep) -> KitDetailOut:
    """Деталка опубликованного кита с офферами по магазинам и вариантами."""
    kit = await session.scalar(
        select(Kit)
        .where(Kit.slug == slug, Kit.status == KitStatus.PUBLISHED)
        .options(selectinload(Kit.items))
    )
    if kit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Кит не найден")

    pricing = await price_kit(session, list(kit.items))
    items = [await _detail_item(session, item, pricing) for item in kit.items]
    return KitDetailOut(
        id=kit.id,
        slug=kit.slug,
        name=kit.name,
        description=kit.description,
        role=kit.role,
        drive_type=kit.drive_type,
        experience_level=kit.experience_level,
        image_url=kit.image_url,
        price_min=pricing.price_min,
        price_max=pricing.price_max,
        complete=pricing.complete,
        items=items,
    )
