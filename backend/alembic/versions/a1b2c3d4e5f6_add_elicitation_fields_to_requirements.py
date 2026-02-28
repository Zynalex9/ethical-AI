"""add elicitation fields to requirements

Revision ID: a1b2c3d4e5f6
Revises: 624c549f6a3b
Create Date: 2026-02-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '624c549f6a3b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'requirements',
        sa.Column(
            'elicited_automatically',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
    )
    op.add_column(
        'requirements',
        sa.Column('elicitation_reason', sa.Text(), nullable=True),
    )
    op.add_column(
        'requirements',
        sa.Column('confidence_score', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('requirements', 'confidence_score')
    op.drop_column('requirements', 'elicitation_reason')
    op.drop_column('requirements', 'elicited_automatically')
