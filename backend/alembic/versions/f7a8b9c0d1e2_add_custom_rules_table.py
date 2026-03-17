"""add custom_rules table

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-03-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f7a8b9c0d1e2"
down_revision: Union[str, None] = "e6f7a8b9c0d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS custom_rules (
            id UUID PRIMARY KEY,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            description TEXT NULL,
            principle VARCHAR(50) NOT NULL DEFAULT 'fairness',
            base_metric VARCHAR(100) NOT NULL,
            aggregation VARCHAR(50) NOT NULL,
            comparison VARCHAR(10) NOT NULL DEFAULT '>=',
            default_threshold DOUBLE PRECISION NOT NULL DEFAULT 0.8,
            created_by_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_custom_rules_project_id ON custom_rules(project_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_custom_rules_project_principle_name "
        "ON custom_rules(project_id, principle, name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_custom_rules_project_principle_name")
    op.execute("DROP INDEX IF EXISTS ix_custom_rules_project_id")
    op.execute("DROP TABLE IF EXISTS custom_rules")
