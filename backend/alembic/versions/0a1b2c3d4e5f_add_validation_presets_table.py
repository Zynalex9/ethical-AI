"""add validation_presets table

Revision ID: 0a1b2c3d4e5f
Revises: f7a8b9c0d1e2
Create Date: 2026-03-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "0a1b2c3d4e5f"
down_revision: Union[str, None] = "f7a8b9c0d1e2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS validation_presets (
            id UUID PRIMARY KEY,
            project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name VARCHAR(255) NOT NULL,
            config JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_by_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_validation_presets_project_id ON validation_presets(project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_validation_presets_created_by_id ON validation_presets(created_by_id)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_validation_presets_project_user_name "
        "ON validation_presets(project_id, created_by_id, name)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_validation_presets_project_user_name")
    op.execute("DROP INDEX IF EXISTS ix_validation_presets_created_by_id")
    op.execute("DROP INDEX IF EXISTS ix_validation_presets_project_id")
    op.execute("DROP TABLE IF EXISTS validation_presets")
