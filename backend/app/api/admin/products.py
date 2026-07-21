"""Админ-API товаров: список с агрегатами, правка, удаление, merge дублей,
привязка/отвязка и создание товара из оффера, массовые операции."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import Select, distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import require_admin
from app.db import SessionDep
from app.models.catalog import Category, KitItem, KitItemCandidate, Offer, Product
from app.models.enums import KitItemType
from app.schemas.catalog import OfferOut
from app.schemas.products import (
    BulkItemResult,
    BulkRequest,
    BulkResult,
    CreateFromOfferOut,
    MergeRequest,
    ProductCatalog,
    ProductDetail,
    ProductOfferRow,
    ProductRow,
    ProductUpdate,
)
from app.services.matching import create_product_from_offer

router = APIRouter(
    prefix="/api/admin", tags=["admin-products"], dependencies=[Depends(require_admin)]
)


class ProductInUseError(Exception):
    """Товар нельзя удалить: он — цель fixed-позиции кита (или офферы в жёстком режиме)."""


def _offers_agg() -> Select:
    """Подзапрос агрегатов по офферам товара (счётчики — по активным, цена — по в наличии)."""
    active = Offer.is_active.is_(True)
    priced = active & Offer.in_stock.is_(True) & Offer.price.is_not(None)
    return (
        select(
            Offer.product_id.label("pid"),
            func.count().filter(active).label("offers_count"),
            func.count(distinct(Offer.shop_id)).filter(active).label("shops_count"),
            func.min(Offer.price).filter(priced).label("price_min"),
            func.max(Offer.price).filter(priced).label("price_max"),
        )
        .where(Offer.product_id.is_not(None))
        .group_by(Offer.product_id)
        .subquery()
    )


async def _get_product(session: AsyncSession, product_id: int) -> Product:
    """Загружает товар или отдаёт 404."""
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    return product


async def _fixed_kit_ids(session: AsyncSession, product_id: int) -> list[int]:
    """kit_id всех fixed-позиций, ссылающихся на товар (мешают удалению)."""
    rows = await session.scalars(
        select(KitItem.kit_id).where(
            KitItem.product_id == product_id, KitItem.item_type == KitItemType.FIXED
        )
    )
    return list(rows.all())


async def _product_detail(session: AsyncSession, product_id: int) -> ProductDetail:
    """Карточка товара: поля + категория + агрегаты + все офферы (вкл. снятые)."""
    product = await session.scalar(
        select(Product)
        .where(Product.id == product_id)
        .options(selectinload(Product.offers).selectinload(Offer.shop))
    )
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Товар не найден")
    category_name = None
    if product.category_id is not None:
        category_name = await session.scalar(
            select(Category.name).where(Category.id == product.category_id)
        )
    # агрегаты по активным офферам (цена — по в наличии с ценой)
    active = [o for o in product.offers if o.is_active]
    priced = [o.price for o in active if o.in_stock and o.price is not None]
    offers = sorted(
        product.offers,
        key=lambda o: (
            not (o.is_active and o.in_stock),  # активные в наличии сначала
            o.price is None,
            o.price or 0,
        ),
    )
    return ProductDetail(
        id=product.id,
        name=product.name,
        slug=product.slug,
        brand=product.brand,
        category_id=product.category_id,
        category_name=category_name,
        description=product.description,
        image_url=product.image_url,
        attrs=product.attrs or {},
        match_key=product.match_key,
        offers_count=len(active),
        shops_count=len({o.shop_id for o in active}),
        price_min=min(priced) if priced else None,
        price_max=max(priced) if priced else None,
        offers=[ProductOfferRow.model_validate(o) for o in offers],
    )


@router.get("/products", response_model=ProductCatalog)
async def list_products(
    session: SessionDep,
    q: Annotated[str | None, Query(description="Подстрока имени (ILIKE, trgm GIN)")] = None,
    category_id: Annotated[int | None, Query()] = None,
    no_category: Annotated[bool, Query(description="Только без категории")] = False,
    multishop: Annotated[bool, Query(description="Только в >1 магазине")] = False,
    sort: Annotated[Literal["name", "created", "offers", "price_min"], Query()] = "name",
    order: Annotated[Literal["asc", "desc"], Query()] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ProductCatalog:
    """Список канонических товаров с агрегатами, поиском, фильтрами и сортировкой."""
    agg = _offers_agg()

    def apply_filters(stmt: Select) -> Select:
        stmt = stmt.outerjoin(agg, agg.c.pid == Product.id)
        if q:
            stmt = stmt.where(Product.name.ilike(f"%{q}%"))
        if no_category:
            stmt = stmt.where(Product.category_id.is_(None))
        elif category_id is not None:
            stmt = stmt.where(Product.category_id == category_id)
        if multishop:
            stmt = stmt.where(func.coalesce(agg.c.shops_count, 0) > 1)
        return stmt

    total = await session.scalar(apply_filters(select(func.count(Product.id))))

    sort_col = {
        "name": Product.name,
        "created": Product.created_at,
        "offers": func.coalesce(agg.c.offers_count, 0),
        "price_min": agg.c.price_min,
    }[sort]
    ordered = sort_col.desc() if order == "desc" else sort_col.asc()
    if sort == "price_min":
        ordered = ordered.nulls_last()

    stmt = apply_filters(
        select(
            Product,
            Category.name,
            func.coalesce(agg.c.offers_count, 0),
            func.coalesce(agg.c.shops_count, 0),
            agg.c.price_min,
            agg.c.price_max,
        ).outerjoin(Category, Category.id == Product.category_id)
    )
    stmt = stmt.order_by(ordered, Product.id).limit(page_size).offset((page - 1) * page_size)

    items: list[ProductRow] = []
    for product, cat_name, offers_count, shops_count, price_min, price_max in (
        await session.execute(stmt)
    ).all():
        items.append(
            ProductRow(
                id=product.id,
                name=product.name,
                slug=product.slug,
                brand=product.brand,
                category_id=product.category_id,
                category_name=cat_name,
                image_url=product.image_url,
                offers_count=offers_count,
                shops_count=shops_count,
                price_min=price_min,
                price_max=price_max,
            )
        )
    return ProductCatalog(items=items, total=total or 0, page=page, page_size=page_size)


@router.get("/products/{product_id}", response_model=ProductDetail)
async def get_product(product_id: int, session: SessionDep) -> ProductDetail:
    """Карточка товара с полями, агрегатами и офферами по магазинам."""
    return await _product_detail(session, product_id)


@router.patch("/products/{product_id}", response_model=ProductDetail)
async def update_product(
    product_id: int, body: ProductUpdate, session: SessionDep
) -> ProductDetail:
    """Правка отображаемых полей товара. `match_key`/`slug` неизменны (ключ матчинга)."""
    product = await _get_product(session, product_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("category_id") is not None:
        if await session.get(Category, data["category_id"]) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена"
            )
    for field, value in data.items():
        setattr(product, field, value)
    await session.commit()
    return await _product_detail(session, product_id)


async def _delete_product(session: AsyncSession, product_id: int, unlink_offers: bool) -> None:
    """Удаляет товар, разбирая FK-ссылки. Кидает ProductInUseError, если удалить нельзя.

    Не коммитит — коммит на вызывающей стороне (эндпоинт или bulk-savepoint)."""
    product = await _get_product(session, product_id)
    kit_ids = await _fixed_kit_ids(session, product_id)
    if kit_ids:
        raise ProductInUseError(f"Товар используется в fixed-позициях китов: {kit_ids}")
    if not unlink_offers:
        has_offers = await session.scalar(
            select(Offer.id).where(Offer.product_id == product_id).limit(1)
        )
        if has_offers is not None:
            raise ProductInUseError("У товара есть офферы (unlink_offers=false)")
    await session.execute(
        update(Offer).where(Offer.product_id == product_id).values(product_id=None)
    )
    await session.execute(
        KitItemCandidate.__table__.delete().where(KitItemCandidate.product_id == product_id)
    )
    await session.delete(product)


@router.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    session: SessionDep,
    unlink_offers: Annotated[bool, Query()] = True,
) -> Response:
    """Удаляет товар: офферы отвязываются, курация чистится. 409, если товар в fixed-ките."""
    try:
        await _delete_product(session, product_id, unlink_offers)
    except ProductInUseError as exc:
        # проверки идут до мутаций — откатывать нечего, коммита не делаем
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/products/{target_id}/merge", response_model=ProductDetail)
async def merge_products(target_id: int, body: MergeRequest, session: SessionDep) -> ProductDetail:
    """Сливает source-товары в цель: офферы/позиции/курация перевешиваются, дубли удаляются."""
    target = await _get_product(session, target_id)
    source_ids = {sid for sid in body.source_ids if sid != target_id}
    existing = set(
        (await session.scalars(select(Product.id).where(Product.id.in_(source_ids)))).all()
    )
    sources = source_ids & existing
    if not sources:  # нечего сливать — идемпотентный no-op
        return await _product_detail(session, target_id)

    # офферы и fixed-позиции китов — без уникальных ограничений, перевешиваем массово
    await session.execute(
        update(Offer).where(Offer.product_id.in_(sources)).values(product_id=target_id)
    )
    await session.execute(
        update(KitItem).where(KitItem.product_id.in_(sources)).values(product_id=target_id)
    )
    await _merge_candidates(session, target_id, sources)

    # дозаполняем пустые поля цели из source
    for src_id in sources:
        src = await session.get(Product, src_id)
        if src is None:
            continue
        if not target.image_url and src.image_url:
            target.image_url = src.image_url
        if not target.description and src.description:
            target.description = src.description
        if not target.brand and src.brand:
            target.brand = src.brand
        await session.delete(src)

    await session.commit()
    return await _product_detail(session, target_id)


async def _merge_candidates(session: AsyncSession, target_id: int, sources: set[int]) -> None:
    """Переносит курацию (kit_item_candidates) на цель, сворачивая флаги OR по kit_item.

    UNIQUE (kit_item_id, product_id) не даёт слить массовым UPDATE, поэтому вручную:
    одна строка на kit_item с product_id=target, флаги — OR по всем исходным строкам.
    """
    rows = list(
        (
            await session.scalars(
                select(KitItemCandidate).where(
                    KitItemCandidate.product_id.in_(sources | {target_id})
                )
            )
        ).all()
    )
    by_item: dict[int, dict[str, bool]] = {}
    for c in rows:
        acc = by_item.setdefault(c.kit_item_id, {"pinned": False, "excluded": False})
        acc["pinned"] = acc["pinned"] or c.is_pinned
        acc["excluded"] = acc["excluded"] or c.is_excluded
    # удаляем все исходные строки, затем создаём по одной на kit_item с целью
    for c in rows:
        await session.delete(c)
    await session.flush()
    for kit_item_id, flags in by_item.items():
        session.add(
            KitItemCandidate(
                kit_item_id=kit_item_id,
                product_id=target_id,
                is_pinned=flags["pinned"],
                is_excluded=flags["excluded"],
            )
        )
    await session.flush()


@router.post("/products/bulk", response_model=BulkResult)
async def bulk_products(body: BulkRequest, session: SessionDep) -> BulkResult:
    """Массовые операции над выбранными товарами (частичные ошибки не роняют пачку)."""
    if body.action == "set_category" and body.category_id is not None:
        if await session.get(Category, body.category_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Категория не найдена"
            )
    results: list[BulkItemResult] = []
    for pid in body.product_ids:
        try:
            async with session.begin_nested():  # savepoint: ошибка одного не рушит остальные
                await _apply_bulk(session, body, pid)
            results.append(BulkItemResult(product_id=pid, ok=True))
        except (ProductInUseError, HTTPException) as exc:
            detail = exc.detail if isinstance(exc, HTTPException) else str(exc)
            results.append(BulkItemResult(product_id=pid, ok=False, error=str(detail)))
    await session.commit()
    succeeded = sum(1 for r in results if r.ok)
    return BulkResult(processed=len(results), succeeded=succeeded, results=results)


async def _apply_bulk(session: AsyncSession, body: BulkRequest, product_id: int) -> None:
    """Применяет одну bulk-операцию к товару (внутри savepoint)."""
    if body.action == "delete":
        await _delete_product(session, product_id, body.unlink_offers)
        return
    product = await _get_product(session, product_id)
    if body.action == "set_category":
        product.category_id = body.category_id
    elif body.action == "set_brand":
        product.brand = body.brand


@router.post("/offers/{offer_id}/unlink", response_model=OfferOut)
async def unlink_offer(offer_id: int, session: SessionDep) -> Offer:
    """Отвязывает оффер от товара (возвращает в пул несматченных)."""
    offer = await session.scalar(
        select(Offer).where(Offer.id == offer_id).options(selectinload(Offer.shop))
    )
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оффер не найден")
    offer.product_id = None
    await session.commit()
    return offer


@router.post("/offers/{offer_id}/create-product", response_model=CreateFromOfferOut)
async def create_product_for_offer(offer_id: int, session: SessionDep) -> CreateFromOfferOut:
    """Создаёт (или находит по match_key) канонический товар из оффера и привязывает его."""
    offer = await session.get(Offer, offer_id)
    if offer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оффер не найден")
    product, created = await create_product_from_offer(session, offer)
    await session.commit()
    detail = await _product_detail(session, product.id)
    return CreateFromOfferOut(product=detail, created=created)
