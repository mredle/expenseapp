# coding=utf-8
"""Add backup_sets and backup_segments tables for logical backup support."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '342dafbb00cb'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'backup_sets',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('backup_type', sa.String(length=32), nullable=False),
        sa.Column('storage_backend', sa.String(length=32), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_segments', sa.Integer(), nullable=True),
        sa.Column('completed_segments', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.String(length=1024), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('db_created_at', sa.DateTime(), nullable=True),
        sa.Column('db_updated_at', sa.DateTime(), nullable=True),
        sa.Column('db_created_by', sa.String(length=64), nullable=True),
        sa.Column('db_updated_by', sa.String(length=64), nullable=True),
        sa.Column('guid', sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_backup_sets_user_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_backup_sets_guid'), 'backup_sets', ['guid'], unique=True)

    op.create_table(
        'backup_segments',
        sa.Column('id', sa.Integer(), sa.Identity(), nullable=False),
        sa.Column('segment_type', sa.String(length=32), nullable=False),
        sa.Column('segment_key', sa.String(length=128), nullable=True),
        sa.Column('segment_label', sa.String(length=256), nullable=True),
        sa.Column('storage_key', sa.String(length=512), nullable=True),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('record_count', sa.Integer(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('checksum', sa.String(length=128), nullable=True),
        sa.Column('error_message', sa.String(length=1024), nullable=True),
        sa.Column('backup_set_id', sa.Integer(), nullable=False),
        sa.Column('db_created_at', sa.DateTime(), nullable=True),
        sa.Column('db_updated_at', sa.DateTime(), nullable=True),
        sa.Column('db_created_by', sa.String(length=64), nullable=True),
        sa.Column('db_updated_by', sa.String(length=64), nullable=True),
        sa.Column('guid', sa.String(length=32), nullable=True),
        sa.ForeignKeyConstraint(['backup_set_id'], ['backup_sets.id'], name='fk_backup_segments_backup_set_id'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_backup_segments_backup_set_id'), 'backup_segments', ['backup_set_id'], unique=False)
    op.create_index(op.f('ix_backup_segments_guid'), 'backup_segments', ['guid'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_backup_segments_guid'), table_name='backup_segments')
    op.drop_index(op.f('ix_backup_segments_backup_set_id'), table_name='backup_segments')
    op.drop_table('backup_segments')
    op.drop_index(op.f('ix_backup_sets_guid'), table_name='backup_sets')
    op.drop_table('backup_sets')
