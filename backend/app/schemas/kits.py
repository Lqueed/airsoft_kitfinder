"""Схемы китов: CRUD кита и позиций, расчёт цены, предпросмотр flexible-позиции."""

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.enums import DriveType, ExperienceLevel, KitItemType, KitStatus, Role
from app.schemas.catalog import ProductOut

# --- Позиции кита ----------------------------------------------------------


class KitItemCreate(BaseModel):
    """Создание позиции кита. fixed → product_id; flexible → category_id."""

    item_type: KitItemType
    title: str
    is_required: bool = True
    sort_order: int = 0
    product_id: int | None = None
    category_id: int | None = None
    max_price: Decimal | None = None
    attr_filters: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _check_target(self) -> "KitItemCreate":
        """fixed требует product_id, flexible — category_id (зеркало CHECK в БД)."""
        if self.item_type is KitItemType.FIXED and self.product_id is None:
            raise ValueError("fixed-позиция требует product_id")
        if self.item_type is KitItemType.FLEXIBLE and self.category_id is None:
            raise ValueError("flexible-позиция требует category_id")
        return self


class KitItemUpdate(BaseModel):
    """Частичное обновление позиции кита."""

    title: str | None = None
    is_required: bool | None = None
    sort_order: int | None = None
    product_id: int | None = None
    category_id: int | None = None
    max_price: Decimal | None = None
    attr_filters: dict[str, Any] | None = None


class KitItemOut(BaseModel):
    """Позиция кита в ответе."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    item_type: KitItemType
    title: str
    is_required: bool
    sort_order: int
    product_id: int | None = None
    product: ProductOut | None = None  # выбранный товар fixed-позиции
    category_id: int | None = None
    max_price: Decimal | None = None
    attr_filters: dict[str, Any] | None = None


class CandidateUpsert(BaseModel):
    """Курация flexible-позиции: закрепить/исключить товар."""

    product_id: int
    is_pinned: bool = False
    is_excluded: bool = False


class CandidateOut(BaseModel):
    """Закреплённый/исключённый товар flexible-позиции."""

    id: int
    product_id: int
    product_name: str
    is_pinned: bool
    is_excluded: bool


# --- Расчёт цены -----------------------------------------------------------


class ItemPricingOut(BaseModel):
    """Цена одной позиции (зеркало services.kit_pricing.ItemPricing)."""

    model_config = ConfigDict(from_attributes=True)

    item_id: int
    title: str
    item_type: KitItemType
    is_required: bool
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    variant_count: int = 0


class KitPricingOut(BaseModel):
    """Вилка цены кита (зеркало services.kit_pricing.KitPricing)."""

    model_config = ConfigDict(from_attributes=True)

    price_min: Decimal | None = None
    price_max: Decimal | None = None
    complete: bool
    items: list[ItemPricingOut] = []


# --- Кит --------------------------------------------------------------------


class KitCreate(BaseModel):
    """Создание кита (черновик)."""

    name: str
    description: str | None = None
    role: Role | None = None
    drive_type: DriveType | None = None
    experience_level: ExperienceLevel | None = None
    image_url: str | None = None


class KitUpdate(BaseModel):
    """Частичное обновление полей кита."""

    name: str | None = None
    description: str | None = None
    role: Role | None = None
    drive_type: DriveType | None = None
    experience_level: ExperienceLevel | None = None
    image_url: str | None = None


class KitListItemOut(BaseModel):
    """Кит в списке (без позиций, с вилкой цены)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    role: Role | None = None
    drive_type: DriveType | None = None
    experience_level: ExperienceLevel | None = None
    status: KitStatus
    image_url: str | None = None
    pricing: KitPricingOut


class KitImageOut(BaseModel):
    """Фото кита: публичный URL, порядок, признак обложки."""

    id: int
    url: str
    is_cover: bool
    sort_order: int


class KitOut(BaseModel):
    """Кит с позициями, фото и вилкой цены."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    slug: str
    name: str
    description: str | None = None
    role: Role | None = None
    drive_type: DriveType | None = None
    experience_level: ExperienceLevel | None = None
    status: KitStatus
    image_url: str | None = None
    items: list[KitItemOut] = []
    images: list[KitImageOut] = []
    pricing: KitPricingOut


# --- Предпросмотр flexible-позиции -----------------------------------------


class FlexibleVariantOut(BaseModel):
    """Вариант flexible-позиции с минимальной ценой покупки."""

    product_id: int
    name: str
    brand: str | None = None
    min_price: Decimal | None = None


class FlexiblePreviewOut(BaseModel):
    """Предпросмотр вариантов flexible-позиции."""

    item_id: int
    variants: list[FlexibleVariantOut] = []
