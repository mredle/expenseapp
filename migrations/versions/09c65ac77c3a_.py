"""empty message

Revision ID: 09c65ac77c3a
Revises: 
Create Date: 2019-03-05 23:33:55.044613

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '09c65ac77c3a'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('images',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('width', sa.Integer(), nullable=True),
    sa.Column('height', sa.Integer(), nullable=True),
    sa.Column('format', sa.String(length=8), nullable=True),
    sa.Column('mode', sa.String(length=8), nullable=True),
    sa.Column('original_filename', sa.String(length=128), nullable=True),
    sa.Column('description', sa.String(length=256), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('currencies',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=3), nullable=True),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('number', sa.Integer(), nullable=True),
    sa.Column('exponent', sa.Integer(), nullable=True),
    sa.Column('inCHF', sa.Float(), nullable=True),
    sa.Column('image_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.String(length=256), nullable=True),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('thumbnails',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('size', sa.Integer(), nullable=True),
    sa.Column('format', sa.String(length=8), nullable=True),
    sa.Column('mode', sa.String(length=8), nullable=True),
    sa.Column('image_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=True),
    sa.Column('email', sa.String(length=128), nullable=True),
    sa.Column('locale', sa.String(length=32), nullable=True),
    sa.Column('timezone', sa.String(length=32), nullable=True),
    sa.Column('password_hash', sa.String(length=128), nullable=True),
    sa.Column('token', sa.String(length=32), nullable=True),
    sa.Column('token_expiration', sa.DateTime(), nullable=True),
    sa.Column('profile_picture_id', sa.Integer(), nullable=True),
    sa.Column('last_message_read_time', sa.DateTime(), nullable=True),
    sa.Column('about_me', sa.String(length=256), nullable=True),
    sa.Column('last_seen', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['profile_picture_id'], ['images.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_token'), 'users', ['token'], unique=True)
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('events',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.Column('admin_id', sa.Integer(), nullable=True),
    sa.Column('accountant_id', sa.Integer(), nullable=True),
    sa.Column('closed', sa.Boolean(), nullable=True),
    sa.Column('image_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.String(length=256), nullable=True),
    sa.ForeignKeyConstraint(['accountant_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_events_date'), 'events', ['date'], unique=False)
    op.create_table('messages',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('body', sa.String(length=256), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('recipient_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_messages_timestamp'), 'messages', ['timestamp'], unique=False)
    op.create_table('notifications',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.Float(), nullable=True),
    sa.Column('payload_json', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_notifications_name'), 'notifications', ['name'], unique=False)
    op.create_index(op.f('ix_notifications_timestamp'), 'notifications', ['timestamp'], unique=False)
    op.create_table('tasks',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=True),
    sa.Column('description', sa.String(length=128), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('complete', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_name'), 'tasks', ['name'], unique=False)
    op.create_table('event_users',
    sa.Column('event_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('event_id', 'user_id')
    )
    op.create_table('expenses',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('currency_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.Float(), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.Column('image_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.String(length=256), nullable=True),
    sa.ForeignKeyConstraint(['currency_id'], ['currencies.id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_expenses_date'), 'expenses', ['date'], unique=False)
    op.create_table('posts',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('body', sa.String(length=256), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_posts_timestamp'), 'posts', ['timestamp'], unique=False)
    op.create_table('settlements',
    sa.Column('db_created_at', sa.DateTime(), nullable=True),
    sa.Column('db_updated_at', sa.DateTime(), nullable=True),
    sa.Column('db_created_by', sa.String(length=64), nullable=True),
    sa.Column('db_updated_by', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=True),
    sa.Column('recipient_id', sa.Integer(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.Column('currency_id', sa.Integer(), nullable=True),
    sa.Column('amount', sa.Float(), nullable=True),
    sa.Column('draft', sa.Boolean(), nullable=True),
    sa.Column('date', sa.DateTime(), nullable=True),
    sa.Column('image_id', sa.Integer(), nullable=True),
    sa.Column('description', sa.String(length=256), nullable=True),
    sa.ForeignKeyConstraint(['currency_id'], ['currencies.id'], ),
    sa.ForeignKeyConstraint(['event_id'], ['events.id'], ),
    sa.ForeignKeyConstraint(['image_id'], ['images.id'], ),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settlements_date'), 'settlements', ['date'], unique=False)
    op.create_table('expense_affected_users',
    sa.Column('expense_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['expense_id'], ['expenses.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('expense_id', 'user_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('expense_affected_users')
    op.drop_index(op.f('ix_settlements_date'), table_name='settlements')
    op.drop_table('settlements')
    op.drop_index(op.f('ix_posts_timestamp'), table_name='posts')
    op.drop_table('posts')
    op.drop_index(op.f('ix_expenses_date'), table_name='expenses')
    op.drop_table('expenses')
    op.drop_table('event_users')
    op.drop_index(op.f('ix_tasks_name'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_index(op.f('ix_notifications_timestamp'), table_name='notifications')
    op.drop_index(op.f('ix_notifications_name'), table_name='notifications')
    op.drop_table('notifications')
    op.drop_index(op.f('ix_messages_timestamp'), table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_events_date'), table_name='events')
    op.drop_table('events')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_index(op.f('ix_users_token'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('thumbnails')
    op.drop_table('currencies')
    op.drop_table('images')
    # ### end Alembic commands ###
