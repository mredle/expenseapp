# coding=utf-8
"""Add read_error flag to files.

Marks files whose backing object could not be read from the storage provider.
Reads are still retried on every access; the flag only suppresses repeated
ERROR-level logging (and the resulting alert emails) and is cleared as soon as
the file becomes readable again.

The column is intentionally nullable with no server_default: this matches the
convention used by every other Boolean column in this project (see
252734b648ed_.py) and is portable across SQLite, MySQL/MariaDB, PostgreSQL and
Oracle. Existing rows get NULL, which is falsy and therefore behaves exactly
like False in application code.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'b7c1f2a3d4e5'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('files', sa.Column('read_error', sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column('files', 'read_error')
