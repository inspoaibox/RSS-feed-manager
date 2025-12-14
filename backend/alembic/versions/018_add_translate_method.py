"""Add translate_method field to feeds and custom_rules.

Revision ID: 018
Revises: 017_add_last_login_at
Create Date: 2024-12-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '018'
down_revision = '017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add translate_method to feeds table
    # Values: 'none', 'ai', 'google'
    op.add_column('feeds', sa.Column('translate_method', sa.String(20), nullable=False, server_default='none'))
    
    # Add translate_method to custom_rules table
    op.add_column('custom_rules', sa.Column('translate_method', sa.String(20), nullable=False, server_default='none'))
    
    # Add google_translate_api_key to users table (for per-user API key)
    op.add_column('users', sa.Column('google_translate_api_key', sa.String(255), nullable=True))
    
    # Migrate existing data: if auto_translate is True, set translate_method to 'ai'
    op.execute("UPDATE feeds SET translate_method = 'ai' WHERE auto_translate = true")
    op.execute("UPDATE custom_rules SET translate_method = 'ai' WHERE auto_translate = true")


def downgrade() -> None:
    op.drop_column('feeds', 'translate_method')
    op.drop_column('custom_rules', 'translate_method')
    op.drop_column('users', 'google_translate_api_key')
