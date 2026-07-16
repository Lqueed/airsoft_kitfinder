"""ORM-модели. Импорт здесь нужен, чтобы Alembic видел все таблицы через Base.metadata."""

from app.models.catalog import (
    Category,
    Kit,
    KitItem,
    KitItemCandidate,
    Offer,
    PriceHistory,
    Product,
    Shop,
)

__all__ = [
    "Category",
    "Kit",
    "KitItem",
    "KitItemCandidate",
    "Offer",
    "PriceHistory",
    "Product",
    "Shop",
]
