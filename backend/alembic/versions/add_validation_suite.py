"""Add validation_suite table

Revision ID: add_validation_suite
Revises: 150479451b70
Create Date: 2025-12-28 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_validation_suite'
down_revision = '150479451b70'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create validation_suites table
    op.create_table(
        'validation_suites',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dataset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('overall_passed', sa.Boolean(), nullable=True),
        sa.Column('fairness_validation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('transparency_validation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('privacy_validation_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.String(length=1000), nullable=True),
        sa.Column('created_by_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dataset_id'], ['datasets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['fairness_validation_id'], ['validations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['model_id'], ['ml_models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['privacy_validation_id'], ['validations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['transparency_validation_id'], ['validations.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index(op.f('ix_validation_suites_model_id'), 'validation_suites', ['model_id'], unique=False)
    op.create_index(op.f('ix_validation_suites_dataset_id'), 'validation_suites', ['dataset_id'], unique=False)
    op.create_index(op.f('ix_validation_suites_status'), 'validation_suites', ['status'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_validation_suites_status'), table_name='validation_suites')
    op.drop_index(op.f('ix_validation_suites_dataset_id'), table_name='validation_suites')
    op.drop_index(op.f('ix_validation_suites_model_id'), table_name='validation_suites')
    
    # Drop table
    op.drop_table('validation_suites')
