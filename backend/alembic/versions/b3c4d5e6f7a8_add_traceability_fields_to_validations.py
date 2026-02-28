"""add traceability fields to validations

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Make requirement_id nullable (validations created from suites may not link to a requirement)
    op.alter_column(
        'validations',
        'requirement_id',
        existing_type=sa.UUID(),
        nullable=True,
    )
    # Change FK ondelete from CASCADE to SET NULL (so deleting a requirement doesn't delete validations)
    op.drop_constraint('validations_requirement_id_fkey', 'validations', type_='foreignkey')
    op.create_foreign_key(
        'validations_requirement_id_fkey',
        'validations',
        'requirements',
        ['requirement_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # Add traceability fields
    op.add_column(
        'validations',
        sa.Column('behavior_pattern', sa.Text(), nullable=True),
    )
    op.add_column(
        'validations',
        sa.Column('affected_groups', postgresql.ARRAY(sa.String()), nullable=True),
    )
    op.add_column(
        'validations',
        sa.Column(
            'feature_contributions',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('validations', 'feature_contributions')
    op.drop_column('validations', 'affected_groups')
    op.drop_column('validations', 'behavior_pattern')

    # Revert FK back to CASCADE
    op.drop_constraint('validations_requirement_id_fkey', 'validations', type_='foreignkey')
    op.create_foreign_key(
        'validations_requirement_id_fkey',
        'validations',
        'requirements',
        ['requirement_id'],
        ['id'],
        ondelete='CASCADE',
    )
    op.alter_column(
        'validations',
        'requirement_id',
        existing_type=sa.UUID(),
        nullable=False,
    )
