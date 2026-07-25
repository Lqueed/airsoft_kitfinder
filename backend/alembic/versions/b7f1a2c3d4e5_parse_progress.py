"""parse_progress table (resumable parsing)

Revision ID: b7f1a2c3d4e5
Revises: 396b27f1d1ad
Create Date: 2026-07-25 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b7f1a2c3d4e5'
down_revision: Union[str, Sequence[str], None] = '396b27f1d1ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'parse_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('shop_code', sa.String(length=64), nullable=False),
        sa.Column('run_started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('done_sections', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('parsed_count', sa.Integer(), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_parse_progress_shop_code'),
        'parse_progress',
        ['shop_code'],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_parse_progress_shop_code'), table_name='parse_progress')
    op.drop_table('parse_progress')
