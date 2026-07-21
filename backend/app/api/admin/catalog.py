"""Админ-API каталога: автокомплит товаров, поиск по каталогу магазина, привязка."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.auth import require_admin
from app.db import SessionDep
from app.models.catalog import Offer, Product, Shop
from app.schemas.catalog import LinkRequest, OfferOut, ProductOut

router = APIRouter(
    prefix="/api/admin", tags=["admin-catalog"], dependencies=[Depends(require_admin)]
)


@router.get("/product-search", response_model=list[ProductOut])
async def search_products(
    session: SessionDep,
    q: Annotated[str | None, Query(description="Подстрока названия")] = None,
    category_id: int | None = None,
    limit: Annotated[int, Query(le=100)] = 20,
) -> list[Product]:
    """Автокомплит товаров для привязки fixed-позиций и офферов."""
    stmt = select(Product).order_by(Product.name).limit(limit)
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    return list((await session.scalars(stmt)).all())


@router.get("/offers", response_model=list[OfferOut])
async def list_offers(
    session: SessionDep,
    shop: Annotated[str | None, Query(description="Код магазина")] = None,
    q: Annotated[str | None, Query(description="Поиск по названию (ILIKE)")] = None,
    status_filter: Annotated[
        Literal["all", "unmatched", "matched"], Query(alias="status")
    ] = "all",
    active: Annotated[bool | None, Query(description="Только активные / снятые")] = None,
    limit: Annotated[int, Query(le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Offer]:
    """Поиск по сырому каталогу магазина (независимо от матчинга).

    Фильтры: магазин, подстрока названия, статус матчинга (all/unmatched/matched),
    активность. Поиск по `raw_title` использует GIN + pg_trgm индекс.
    """
    stmt = (
        select(Offer)
        .order_by(Offer.raw_title)
        .limit(limit)
        .offset(offset)
        .options(selectinload(Offer.shop))
    )
    if shop:
        stmt = stmt.where(
            Offer.shop_id == select(Shop.id).where(Shop.code == shop).scalar_subquery()
        )
    if q:
        stmt = stmt.where(Offer.raw_title.ilike(f"%{q}%"))
    if status_filter == "unmatched":
        stmt = stmt.where(Offer.product_id.is_(None))
    elif status_filter == "matched":
        stmt = stmt.where(Offer.product_id.is_not(None))
    if active is not None:
        stmt = stmt.where(Offer.is_active.is_(active))
    return list((await session.scalars(stmt)).all())


@router.post("/offers/{offer_id}/link", response_model=OfferOut)
async def link_offer(offer_id: int, body: LinkRequest, session: SessionDep) -> Offer:
    """Привязывает оффер к каноническому товару (ручная доразметка)."""
    offer = await session.scalar(
        select(Offer).where(Offer.id == offer_id).options(selectinload(Offer.shop))
    )
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оффер не найден")
    if await session.get(Product, body.product_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    offer.product_id = body.product_id
    await session.commit()
    return offer
