"""offers raw_title pg_trgm search index

Revision ID: de92e57438d3
Revises: 205a64dde915
Create Date: 2026-07-17 10:49:54.608526

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'de92e57438d3'
down_revision: Union[str, Sequence[str], None] = '205a64dde915'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Включает pg_trgm и GIN-индекс для быстрого ILIKE-поиска по названию оффера."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_offers_raw_title_trgm",
        "offers",
        ["raw_title"],
        postgresql_using="gin",
        postgresql_ops={"raw_title": "gin_trgm_ops"},
    )


def downgrade() -> None:
    """Убирает индекс (расширение pg_trgm оставляем — им могут пользоваться другие)."""
    op.drop_index("ix_offers_raw_title_trgm", table_name="offers")
