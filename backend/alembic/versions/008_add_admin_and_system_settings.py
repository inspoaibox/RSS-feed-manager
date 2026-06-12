"""Add admin field and system settings table.

Revision ID: 008
Revises: 007
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008'
down_revision: Union[str, None] = '007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column['name'] for column in inspector.get_columns('users')}
    tables = set(inspector.get_table_names())

    # Add is_admin column to users table
    if 'is_admin' not in user_columns:
        op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='false'))
    
    # Set first user as admin
    op.execute("UPDATE users SET is_admin = true WHERE id = (SELECT MIN(id) FROM users)")
    
    # Make column not nullable
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('is_admin', nullable=False, server_default=None)
    
    # Create system_settings table
    if 'system_settings' not in tables:
        op.create_table(
            'system_settings',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('key', sa.String(100), nullable=False),
            sa.Column('value', sa.Text(), nullable=True),
            sa.Column('description', sa.String(500), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('ix_system_settings_key', 'system_settings', ['key'], unique=True)
    
    # Insert default settings
    if bind.dialect.name == 'sqlite':
        op.execute("""
            INSERT OR IGNORE INTO system_settings (key, value, description, created_at)
            VALUES ('allow_registration', 'true', '是否允许新用户注册', CURRENT_TIMESTAMP)
        """)
    else:
        op.execute("""
            INSERT INTO system_settings (key, value, description, created_at)
            SELECT 'allow_registration', 'true', '是否允许新用户注册', CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM system_settings WHERE key = 'allow_registration'
            )
        """)


def downgrade() -> None:
    op.drop_index('ix_system_settings_key', table_name='system_settings')
    op.drop_table('system_settings')
    op.drop_column('users', 'is_admin')
