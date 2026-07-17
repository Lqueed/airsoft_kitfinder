"""Схемы публичной витрины: карточка кита в каталоге и деталка кита."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import KitItemType
from app.schemas.catalog import ShopBrief


class KitCardOut(BaseModel):
    """Кит в каталоге (карточка): краткие поля + вилка цены."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    role: str | None = None
    drive_type: str | None = None
    experience_level: str | None = None
    image_url: str | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    complete: bool


class KitCatalogOut(BaseModel):
    """Страница каталога китов с пагинацией."""

    items: list[KitCardOut]
    total: int
    page: int
    page_size: int


class ProductBrief(BaseModel):
    """Товар для витрины (без служебных полей)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    brand: str | None = None
    image_url: str | None = None


class OfferView(BaseModel):
    """Предложение магазина по товару (для кнопки «Купить»)."""

    shop: ShopBrief
    price: Decimal | None = None
    in_stock: bool
    url: str


class VariantView(BaseModel):
    """Вариант flexible-позиции: товар, его минимальная цена и офферы по магазинам."""

    product: ProductBrief
    min_price: Decimal | None = None
    offers: list[OfferView] = []


class KitDetailItemOut(BaseModel):
    """Позиция кита на деталке. fixed → product+offers; flexible → variants."""

    id: int
    title: str
    item_type: KitItemType
    is_required: bool
    sort_order: int
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    # fixed
    product: ProductBrief | None = None
    offers: list[OfferView] = []
    # flexible
    variants: list[VariantView] = []


class KitDetailOut(BaseModel):
    """Деталка кита: поля, вилка и позиции с офферами/вариантами."""

    id: int
    slug: str
    name: str
    description: str | None = None
    role: str | None = None
    drive_type: str | None = None
    experience_level: str | None = None
    image_url: str | None = None
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    complete: bool
    items: list[KitDetailItemOut] = []
