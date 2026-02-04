"""Create initial database schema with all tables

Revision ID: 001
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all tables for the AI Finance Platform."""
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create connections table
    op.create_table(
        'connections',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('institution_id', sa.String(length=100), nullable=False),
        sa.Column('institution_name', sa.String(length=200), nullable=False),
        sa.Column('access_token', sa.Text(), nullable=False),
        sa.Column('last_sync', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'EXPIRED', 'ERROR')", name='check_connection_status'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_connections_id'), 'connections', ['id'], unique=False)
    op.create_index(op.f('ix_connections_user_id'), 'connections', ['user_id'], unique=False)
    op.create_index(op.f('ix_connections_status'), 'connections', ['status'], unique=False)
    op.create_index('idx_connections_user_status', 'connections', ['user_id', 'status'], unique=False)
    op.create_index('idx_connections_user_institution', 'connections', ['user_id', 'institution_id'], unique=False)

    # Create transactions table
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('type', sa.String(length=10), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('confidence_score', sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column('connection_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("type IN ('INCOME', 'EXPENSE')", name='check_transaction_type'),
        sa.CheckConstraint("source IN ('MANUAL', 'API', 'FILE_IMPORT')", name='check_transaction_source'),
        sa.CheckConstraint('amount >= 0', name='check_amount_positive'),
        sa.CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 1)",
            name='check_confidence_score_range'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['connection_id'], ['connections.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_transactions_id'), 'transactions', ['id'], unique=False)
    op.create_index(op.f('ix_transactions_user_id'), 'transactions', ['user_id'], unique=False)
    op.create_index(op.f('ix_transactions_date'), 'transactions', ['date'], unique=False)
    op.create_index(op.f('ix_transactions_category'), 'transactions', ['category'], unique=False)
    op.create_index('idx_transactions_user_date', 'transactions', ['user_id', 'date'], unique=False)
    op.create_index('idx_transactions_user_category', 'transactions', ['user_id', 'category'], unique=False)
    op.create_index('idx_transactions_user_type', 'transactions', ['user_id', 'type'], unique=False)
    op.create_index('idx_transactions_deleted', 'transactions', ['deleted_at'], unique=False)

    # Create budgets table
    op.create_table(
        'budgets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('allocations', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_budgets_id'), 'budgets', ['id'], unique=False)
    op.create_index(op.f('ix_budgets_user_id'), 'budgets', ['user_id'], unique=False)
    op.create_index(op.f('ix_budgets_period_start'), 'budgets', ['period_start'], unique=False)
    op.create_index(op.f('ix_budgets_period_end'), 'budgets', ['period_end'], unique=False)
    op.create_index('idx_budgets_user_period', 'budgets', ['user_id', 'period_start', 'period_end'], unique=False)

    # Create financial_goals table
    op.create_table(
        'financial_goals',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('target_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('current_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('deadline', sa.Date(), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint("status IN ('ACTIVE', 'ACHIEVED', 'ARCHIVED')", name='check_goal_status'),
        sa.CheckConstraint('target_amount > 0', name='check_target_amount_positive'),
        sa.CheckConstraint('current_amount >= 0', name='check_current_amount_non_negative'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_financial_goals_id'), 'financial_goals', ['id'], unique=False)
    op.create_index(op.f('ix_financial_goals_user_id'), 'financial_goals', ['user_id'], unique=False)
    op.create_index(op.f('ix_financial_goals_status'), 'financial_goals', ['status'], unique=False)
    op.create_index('idx_financial_goals_user_status', 'financial_goals', ['user_id', 'status'], unique=False)
    op.create_index('idx_financial_goals_user_deadline', 'financial_goals', ['user_id', 'deadline'], unique=False)

    # Create ml_models table
    op.create_table(
        'ml_models',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('model_type', sa.String(length=50), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.String(length=20), nullable=False),
        sa.Column('accuracy', sa.Float(), nullable=True),
        sa.Column('precision', sa.Float(), nullable=True),
        sa.Column('recall', sa.Float(), nullable=True),
        sa.Column('trained_at', sa.DateTime(), nullable=False),
        sa.Column('model_path', sa.String(length=500), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.CheckConstraint("model_type IN ('CATEGORIZATION', 'PREDICTION')", name='check_model_type'),
        sa.CheckConstraint(
            "accuracy IS NULL OR (accuracy >= 0 AND accuracy <= 1)",
            name='check_accuracy_range'
        ),
        sa.CheckConstraint(
            "precision IS NULL OR (precision >= 0 AND precision <= 1)",
            name='check_precision_range'
        ),
        sa.CheckConstraint(
            "recall IS NULL OR (recall >= 0 AND recall <= 1)",
            name='check_recall_range'
        ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_ml_models_id'), 'ml_models', ['id'], unique=False)
    op.create_index(op.f('ix_ml_models_model_type'), 'ml_models', ['model_type'], unique=False)
    op.create_index(op.f('ix_ml_models_is_active'), 'ml_models', ['is_active'], unique=False)
    op.create_index('idx_ml_models_type_active', 'ml_models', ['model_type', 'is_active'], unique=False)
    op.create_index('idx_ml_models_user_type', 'ml_models', ['user_id', 'model_type'], unique=False)
    op.create_index('idx_ml_models_user_type_active', 'ml_models', ['user_id', 'model_type', 'is_active'], unique=False)


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('ml_models')
    op.drop_table('financial_goals')
    op.drop_table('budgets')
    op.drop_table('transactions')
    op.drop_table('connections')
    op.drop_table('users')
