"""ORM-модели каталога: магазины, товары, офферы, цены, киты и их позиции."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import (
    DriveType,
    ExperienceLevel,
    KitItemType,
    KitStatus,
    Role,
)


def _enum_values(enum_cls: type) -> list[str]:
    """Хранить в БД значения enum (.value), а не имена членов — чтобы совпадало
    с CHECK-констрейнтами (`'fixed'`/`'flexible'`) и валидацией Pydantic на чтении."""
    return [member.value for member in enum_cls]


class Shop(Base):
    """Магазин-источник. `code` совпадает с кодом парсера-плагина."""

    __tablename__ = "shops"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    base_url: Mapped[str] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    offers: Mapped[list["Offer"]] = relationship(back_populates="shop")


class Category(Base):
    """Наша собственная таксономия товаров (дерево глубины 1)."""

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))


class Product(Base):
    """Каноническая сущность товара (одна на модель, независимо от магазина)."""

    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(512))
    slug: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    brand: Mapped[str | None] = mapped_column(String(255))
    # Нормализованное имя для авто-матчинга офферов между магазинами
    match_key: Mapped[str] = mapped_column(String(512), index=True)
    # Свободные атрибуты (тип привода, материал и т.п.); GIN-индекс — в миграции
    attrs: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    offers: Mapped[list["Offer"]] = relationship(back_populates="product")


class Offer(Base):
    """Предложение конкретного магазина по товару."""

    __tablename__ = "offers"
    __table_args__ = (
        UniqueConstraint("shop_id", "external_id", name="uq_offers_shop_external"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    # null = оффер ещё не сматчен с каноническим товаром
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    url: Mapped[str] = mapped_column(String(1024))
    raw_title: Mapped[str] = mapped_column(String(512))
    raw_category: Mapped[str | None] = mapped_column(String(512))
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    in_stock: Mapped[bool] = mapped_column(default=True)
    # false = оффер пропал с сайта (не удаляем — история и «воскрешение»)
    is_active: Mapped[bool] = mapped_column(default=True)
    image_url: Mapped[str | None] = mapped_column(String(1024))
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    shop: Mapped["Shop"] = relationship(back_populates="offers")
    product: Mapped["Product | None"] = relationship(back_populates="offers")


class PriceHistory(Base):
    """История цен оффера. Запись добавляется только при изменении цены/наличия."""

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    offer_id: Mapped[int] = mapped_column(ForeignKey("offers.id"), index=True)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    in_stock: Mapped[bool] = mapped_column()
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Kit(Base):
    """Кит — заранее собранный набор снаряжения."""

    __tablename__ = "kits"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    role: Mapped[Role | None] = mapped_column(
        Enum(Role, native_enum=False, length=32, values_callable=_enum_values)
    )
    drive_type: Mapped[DriveType | None] = mapped_column(
        Enum(DriveType, native_enum=False, length=32, values_callable=_enum_values)
    )
    experience_level: Mapped[ExperienceLevel | None] = mapped_column(
        Enum(ExperienceLevel, native_enum=False, length=32, values_callable=_enum_values)
    )
    status: Mapped[KitStatus] = mapped_column(
        Enum(KitStatus, native_enum=False, length=32, values_callable=_enum_values),
        default=KitStatus.DRAFT,
        index=True,
    )
    image_url: Mapped[str | None] = mapped_column(String(1024))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list["KitItem"]] = relationship(
        back_populates="kit", cascade="all, delete-orphan", order_by="KitItem.sort_order"
    )


class KitItem(Base):
    """Позиция кита. Оба типа (fixed/flexible) в одной таблице с дискриминатором."""

    __tablename__ = "kit_items"
    __table_args__ = (
        CheckConstraint(
            "(item_type = 'fixed' AND product_id IS NOT NULL) "
            "OR (item_type = 'flexible' AND category_id IS NOT NULL)",
            name="ck_kit_items_type_target",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kit_id: Mapped[int] = mapped_column(ForeignKey("kits.id", ondelete="CASCADE"), index=True)
    sort_order: Mapped[int] = mapped_column(default=0)
    item_type: Mapped[KitItemType] = mapped_column(
        Enum(KitItemType, native_enum=False, length=32, values_callable=_enum_values)
    )
    title: Mapped[str] = mapped_column(String(255))
    is_required: Mapped[bool] = mapped_column(default=True)

    # fixed: конкретный товар
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    # flexible: категория + критерии подбора
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))
    max_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    attr_filters: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    kit: Mapped["Kit"] = relationship(back_populates="items")
    candidates: Mapped[list["KitItemCandidate"]] = relationship(
        back_populates="kit_item", cascade="all, delete-orphan"
    )


class KitItemCandidate(Base):
    """Ручная курация вариантов flexible-позиции: закреплённые и исключённые товары."""

    __tablename__ = "kit_item_candidates"
    __table_args__ = (
        UniqueConstraint("kit_item_id", "product_id", name="uq_candidate_item_product"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kit_item_id: Mapped[int] = mapped_column(
        ForeignKey("kit_items.id", ondelete="CASCADE"), index=True
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    is_pinned: Mapped[bool] = mapped_column(default=False)
    is_excluded: Mapped[bool] = mapped_column(default=False)

    kit_item: Mapped["KitItem"] = relationship(back_populates="candidates")
