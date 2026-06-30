"""add pending voice confirmations

Revision ID: a3f9c1d8e224
Revises: 74f222f5d82f
Create Date: 2026-06-30 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3f9c1d8e224'
down_revision: Union[str, None] = '74f222f5d82f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('pending_voice_confirmations',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('intent', sa.String(length=50), nullable=False),
    sa.Column('target_id', sa.UUID(), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_pending_voice_confirmations_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_pending_voice_confirmations'))
    )
    op.create_index(op.f('ix_pending_voice_confirmations_user_id'), 'pending_voice_confirmations', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pending_voice_confirmations_user_id'), table_name='pending_voice_confirmations')
    op.drop_table('pending_voice_confirmations')
