"""Публичный умный поиск по товарам и карточка сравнения цен (M9).

Отдельный от китов пользовательский сценарий: найти конкретный товар и увидеть,
где он дешевле — список магазинов с ценой, наличием и ссылкой. Витрина над готовой
моделью `products`/`offers`; ценность напрямую зависит от качества матчинга (M3/M10):
один товар должен агрегировать офферы разных магазинов, иначе сравнивать нечего.
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import distinct, func, select, text
from sqlalchemy.orm import selectinload

from app.db import SessionDep
from app.models.catalog import Offer, Product
from app.schemas.catalog import ShopBrief
from app.schemas.public import (
    OfferView,
    ProductComparisonOut,
    ProductSearchOut,
    ProductSearchRow,
)

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("/search", response_model=ProductSearchOut)
async def search_products(
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, description="Название товара")],
    limit: Annotated[int, Query(ge=1, le=50)] = 24,
) -> ProductSearchOut:
    """Поиск канонического товара по названию (pg_trgm, терпим к опечаткам).

    Возвращает только товары, у которых есть хотя бы один доступный к покупке оффер
    (активный, в наличии, с ценой) — иначе сравнивать цены не по чему. Сортировка:
    сначала по близости названия к запросу, при равенстве — дешевле выше.
    """
    # Порог word_similarity в рамках транзакции запроса (устойчивость к опечаткам),
    # как в поиске китов: совпадение слова внутри длинного названия товара.
    await session.execute(text("SET LOCAL pg_trgm.word_similarity_threshold = 0.3"))

    active = Offer.is_active.is_(True)
    priced = active & Offer.in_stock.is_(True) & Offer.price.is_not(None)
    sim = func.word_similarity(q, Product.name)
    price_min = func.min(Offer.price).filter(priced)

    stmt = (
        select(
            Product,
            price_min.label("price_min"),
            func.count(distinct(Offer.shop_id)).filter(priced).label("shops_count"),
        )
        .join(Offer, Offer.product_id == Product.id)
        .where(Product.name.op("%>")(q))
        .group_by(Product.id)
        .having(func.count().filter(priced) > 0)  # есть что купить/сравнить
        .order_by(sim.desc(), price_min.asc().nulls_last())
        .limit(limit)
    )
    items = [
        ProductSearchRow(
            id=product.id,
            slug=product.slug,
            name=product.name,
            brand=product.brand,
            image_url=product.image_url,
            price_min=pmin,
            shops_count=shops_count,
        )
        for product, pmin, shops_count in (await session.execute(stmt)).all()
    ]
    return ProductSearchOut(items=items, total=len(items))


@router.get("/{slug}", response_model=ProductComparisonOut)
async def get_product(slug: str, session: SessionDep) -> ProductComparisonOut:
    """Карточка товара: все активные офферы по магазинам, дешёвые/в наличии — сверху.

    Недоступные (нет в наличии или без цены) не отбрасываются, а показываются ниже
    с пометкой наличия — чтобы пользователь видел полный расклад по магазинам.
    """
    product = await session.scalar(
        select(Product)
        .where(Product.slug == slug)
        .options(selectinload(Product.offers).selectinload(Offer.shop))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")

    active = [offer for offer in product.offers if offer.is_active]
    buyable = [o.price for o in active if o.in_stock and o.price is not None]
    # в наличии с ценой → сначала; затем по возрастанию цены (None — в конец)
    offers_sorted = sorted(
        active,
        key=lambda o: (not (o.in_stock and o.price is not None), o.price is None, o.price or 0),
    )
    return ProductComparisonOut(
        id=product.id,
        slug=product.slug,
        name=product.name,
        brand=product.brand,
        image_url=product.image_url,
        description=product.description,
        price_min=min(buyable) if buyable else None,
        price_max=max(buyable) if buyable else None,
        shops_count=len({o.shop_id for o in active if o.in_stock and o.price is not None}),
        offers=[
            OfferView(
                shop=ShopBrief.model_validate(offer.shop),
                price=offer.price,
                in_stock=offer.in_stock,
                url=offer.url,
            )
            for offer in offers_sorted
        ],
    )
