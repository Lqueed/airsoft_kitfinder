"""Схемы админ-управления товарами: список с агрегатами, карточка, правка, merge, bulk."""

from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.catalog import ShopBrief


class ProductRow(BaseModel):
    """Строка списка товаров с агрегатами по офферам."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    brand: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    image_url: str | None = None
    offers_count: int = 0
    shops_count: int = 0
    price_min: Decimal | None = None
    price_max: Decimal | None = None


class ProductCatalog(BaseModel):
    """Страница списка товаров."""

    items: list[ProductRow]
    total: int
    page: int
    page_size: int


class ProductOfferRow(BaseModel):
    """Оффер в карточке товара (все, включая снятые)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    shop: ShopBrief
    raw_title: str
    raw_category: str | None = None
    price: Decimal | None = None
    in_stock: bool
    is_active: bool
    url: str


class ProductDetail(BaseModel):
    """Карточка товара: поля + агрегаты + список офферов."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    brand: str | None = None
    category_id: int | None = None
    category_name: str | None = None
    description: str | None = None
    image_url: str | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)
    match_key: str  # read-only, для информации (не редактируется)
    offers_count: int = 0
    shops_count: int = 0
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    offers: list[ProductOfferRow] = Field(default_factory=list)


class ProductUpdate(BaseModel):
    """Частичная правка полей товара. `match_key`/`slug` не меняются."""

    name: str | None = None
    brand: str | None = None
    category_id: int | None = None
    description: str | None = None
    image_url: str | None = None
    attrs: dict[str, Any] | None = None


class MergeRequest(BaseModel):
    """Слияние дублей: source-товары вливаются в товар-цель (из пути)."""

    source_ids: Annotated[list[int], Field(min_length=1)]


class CreateFromOfferOut(BaseModel):
    """Результат создания товара из оффера (find-or-create)."""

    product: ProductDetail
    created: bool


# --- Массовые операции (discriminated union по action) ----------------------


class BulkSetCategory(BaseModel):
    action: Literal["set_category"]
    product_ids: Annotated[list[int], Field(min_length=1)]
    category_id: int | None = None


class BulkSetBrand(BaseModel):
    action: Literal["set_brand"]
    product_ids: Annotated[list[int], Field(min_length=1)]
    brand: str | None = None


class BulkDelete(BaseModel):
    action: Literal["delete"]
    product_ids: Annotated[list[int], Field(min_length=1)]
    unlink_offers: bool = True


BulkRequest = Annotated[BulkSetCategory | BulkSetBrand | BulkDelete, Field(discriminator="action")]


class BulkItemResult(BaseModel):
    """Результат операции над одним товаром (частичные ошибки не роняют пачку)."""

    product_id: int
    ok: bool
    error: str | None = None


class BulkResult(BaseModel):
    processed: int
    succeeded: int
    results: list[BulkItemResult]
