"""widen error_message columns to TEXT

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-03-07 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd5e6f7a8b9c0'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'validations', 'error_message',
        existing_type=sa.String(1000),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        'validation_suites', 'error_message',
        existing_type=sa.String(1000),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'validation_suites', 'error_message',
        existing_type=sa.Text(),
        type_=sa.String(1000),
        existing_nullable=True,
    )
    op.alter_column(
        'validations', 'error_message',
        existing_type=sa.Text(),
        type_=sa.String(1000),
        existing_nullable=True,
    )
