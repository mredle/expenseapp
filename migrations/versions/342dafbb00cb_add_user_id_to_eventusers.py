# coding=utf-8
"""Add user_id FK column to eventusers table."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '342dafbb00cb'
down_revision = '8a6b6ed02c0f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('eventusers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_eventusers_user_id'), ['user_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_eventusers_user_id_users',
            'users',
            ['user_id'],
            ['id'],
        )


def downgrade() -> None:
    with op.batch_alter_table('eventusers', schema=None) as batch_op:
        batch_op.drop_constraint('fk_eventusers_user_id_users', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_eventusers_user_id'))
        batch_op.drop_column('user_id')
