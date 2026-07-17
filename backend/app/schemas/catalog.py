"""Схемы каталога: товары, офферы, привязка оффера к товару."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ShopBrief(BaseModel):
    """Краткая карточка магазина (для отображения оффера)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str


class ProductOut(BaseModel):
    """Товар для автокомплита при сборке fixed-позиций и привязке офферов."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    brand: str | None = None
    category_id: int | None = None
    image_url: str | None = None


class OfferOut(BaseModel):
    """Оффер магазина (для экрана несматченных офферов)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_title: str
    raw_category: str | None = None
    price: Decimal | None = None
    in_stock: bool
    url: str
    product_id: int | None = None
    shop: ShopBrief


class LinkRequest(BaseModel):
    """Запрос на привязку оффера к каноническому товару."""

    product_id: int
