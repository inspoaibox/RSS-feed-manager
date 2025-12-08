"""Initial database schema

Revision ID: 001
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(50), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('ix_users_username', 'users', ['username'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Categories table
    op.create_table(
        'categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('user_id', 'name', name='uq_category_user_name'),
    )
    op.create_index('ix_categories_user_id', 'categories', ['user_id'])

    # Feeds table
    op.create_table(
        'feeds',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('url', sa.String(2048), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('site_url', sa.String(2048), nullable=True),
        sa.Column('icon_url', sa.String(2048), nullable=True),
        sa.Column('fetch_interval', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('last_fetched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('auto_translate', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('auto_summarize', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('target_language', sa.String(10), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_feeds_user_id', 'feeds', ['user_id'])
    op.create_index('ix_feeds_category_id', 'feeds', ['category_id'])

    # Articles table
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('feed_id', sa.Integer(), nullable=False),
        sa.Column('guid', sa.String(2048), nullable=False),
        sa.Column('link', sa.String(2048), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('full_content', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('translation', sa.Text(), nullable=True),
        sa.Column('author', sa.String(255), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cached_images', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['feed_id'], ['feeds.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('feed_id', 'guid', name='uq_article_feed_guid'),
    )
    op.create_index('ix_articles_feed_id', 'articles', ['feed_id'])

    # UserArticles table (association table for read/favorite status)
    op.create_table(
        'user_articles',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_favorite', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('favorited_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('user_id', 'article_id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
    )

    # AI Providers table
    op.create_table(
        'ai_providers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('type', sa.String(50), nullable=False),
        sa.Column('api_key', sa.String(500), nullable=False),
        sa.Column('base_url', sa.String(2048), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_ai_providers_user_id', 'ai_providers', ['user_id'])

    # AI Models table
    op.create_table(
        'ai_models',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('provider_id', sa.Integer(), nullable=False),
        sa.Column('model_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(500), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['provider_id'], ['ai_providers.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_ai_models_provider_id', 'ai_models', ['provider_id'])

    # Custom Rules table
    op.create_table(
        'custom_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('target_url', sa.String(2048), nullable=False),
        sa.Column('list_selector', sa.String(500), nullable=False),
        sa.Column('title_selector', sa.String(500), nullable=False),
        sa.Column('link_selector', sa.String(500), nullable=False),
        sa.Column('content_selector', sa.String(500), nullable=True),
        sa.Column('date_selector', sa.String(500), nullable=True),
        sa.Column('fetch_interval', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('last_fetched_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('error_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('auto_translate', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('auto_summarize', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('target_language', sa.String(10), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_custom_rules_user_id', 'custom_rules', ['user_id'])
    op.create_index('ix_custom_rules_category_id', 'custom_rules', ['category_id'])


def downgrade() -> None:
    op.drop_table('custom_rules')
    op.drop_table('ai_models')
    op.drop_table('ai_providers')
    op.drop_table('user_articles')
    op.drop_table('articles')
    op.drop_table('feeds')
    op.drop_table('categories')
    op.drop_table('users')
