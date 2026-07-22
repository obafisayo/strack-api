"""avatar_url column to TEXT for base64 data URL storage

Revision ID: c4d5e6f7a8b9
Revises: a3f9c1d8e224
Create Date: 2026-07-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'a3f9c1d8e224'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'users',
        'avatar_url',
        type_=sa.Text(),
        existing_type=sa.String(500),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        'users',
        'avatar_url',
        type_=sa.String(500),
        existing_type=sa.Text(),
        existing_nullable=True,
        postgresql_using='avatar_url::varchar(500)',
    )
