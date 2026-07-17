"""trgm search indexes on kits.name and products.name

Revision ID: c7d181e9cc6a
Revises: de92e57438d3
Create Date: 2026-07-17 12:53:27.591447

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d181e9cc6a'
down_revision: Union[str, Sequence[str], None] = 'de92e57438d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """GIN-индексы pg_trgm для поиска китов по названию и товарам состава."""
    op.create_index(
        "ix_kits_name_trgm", "kits", ["name"],
        postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_products_name_trgm", "products", ["name"],
        postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"},
    )


def downgrade() -> None:
    """Убирает индексы поиска."""
    op.drop_index("ix_products_name_trgm", table_name="products")
    op.drop_index("ix_kits_name_trgm", table_name="kits")
