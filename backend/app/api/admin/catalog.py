"""Админ-API каталога: автокомплит товаров, несматченные офферы, ручная привязка."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.auth import require_admin
from app.db import SessionDep
from app.models.catalog import Offer, Product
from app.schemas.catalog import LinkRequest, OfferOut, ProductOut

router = APIRouter(
    prefix="/api/admin", tags=["admin-catalog"], dependencies=[Depends(require_admin)]
)


@router.get("/products", response_model=list[ProductOut])
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
    unmatched: bool = False,
    limit: Annotated[int, Query(le=200)] = 50,
) -> list[Offer]:
    """Офферы магазинов; `unmatched=true` — только без привязки к товару."""
    stmt = (
        select(Offer)
        .order_by(Offer.first_seen_at.desc())
        .limit(limit)
        .options(selectinload(Offer.shop))
    )
    if unmatched:
        stmt = stmt.where(Offer.product_id.is_(None))
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
