"""Initial migration with endpoints, check_results, and notification_logs

Revision ID: 6efa52dc99ab
Revises: 
Create Date: 2025-10-26 21:21:35.585455

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6efa52dc99ab'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create endpoints table
    op.create_table(
        'endpoints',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('method', sa.String(length=10), nullable=False),
        sa.Column('interval', sa.Integer(), nullable=False),
        sa.Column('timeout', sa.Integer(), nullable=False),
        sa.Column('expected_status', sa.Integer(), nullable=False),
        sa.Column('headers', sa.JSON(), nullable=True),
        sa.Column('body', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_endpoints_id'), 'endpoints', ['id'], unique=False)
    op.create_index(op.f('ix_endpoints_is_active'), 'endpoints', ['is_active'], unique=False)
    op.create_index(op.f('ix_endpoints_name'), 'endpoints', ['name'], unique=True)

    # Create check_results table
    op.create_table(
        'check_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('endpoint_id', sa.Integer(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('response_time', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('checked_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_check_results_checked_at'), 'check_results', ['checked_at'], unique=False)
    op.create_index(op.f('ix_check_results_endpoint_id'), 'check_results', ['endpoint_id'], unique=False)
    op.create_index(op.f('ix_check_results_id'), 'check_results', ['id'], unique=False)

    # Create notification_logs table
    op.create_table(
        'notification_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('endpoint_id', sa.Integer(), nullable=False),
        sa.Column('notification_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['endpoint_id'], ['endpoints.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notification_logs_endpoint_id'), 'notification_logs', ['endpoint_id'], unique=False)
    op.create_index(op.f('ix_notification_logs_id'), 'notification_logs', ['id'], unique=False)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_notification_logs_id'), table_name='notification_logs')
    op.drop_index(op.f('ix_notification_logs_endpoint_id'), table_name='notification_logs')
    op.drop_table('notification_logs')
    
    op.drop_index(op.f('ix_check_results_id'), table_name='check_results')
    op.drop_index(op.f('ix_check_results_endpoint_id'), table_name='check_results')
    op.drop_index(op.f('ix_check_results_checked_at'), table_name='check_results')
    op.drop_table('check_results')
    
    op.drop_index(op.f('ix_endpoints_name'), table_name='endpoints')
    op.drop_index(op.f('ix_endpoints_is_active'), table_name='endpoints')
    op.drop_index(op.f('ix_endpoints_id'), table_name='endpoints')
    op.drop_table('endpoints')
