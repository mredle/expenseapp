"""empty message

Revision ID: 1fdbb8e40591
Revises: 6d324b095431
Create Date: 2020-04-13 18:10:03.654533

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1fdbb8e40591'
down_revision = '6d324b095431'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('currencies', sa.Column('source', sa.String(length=32), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('currencies', 'source')
    # ### end Alembic commands ###
