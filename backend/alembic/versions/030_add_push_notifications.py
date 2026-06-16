"""Add push notification tables

Revision ID: 030_add_push_notifications
Revises: 029_add_translation_scope
Create Date: 2026-06-16 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '030_add_push_notifications'
down_revision = '029_add_translation_scope'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 创建推送订阅规则表
    op.create_table(
        'notification_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('subscription_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('keyword', sa.String(length=500), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('browser_notification', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('desktop_notification', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('quiet_hours', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notification_subscriptions_user_id', 'notification_subscriptions', ['user_id'])
    op.create_index('ix_notification_subscriptions_target_id', 'notification_subscriptions', ['target_id'])
    op.create_index('ix_notification_subscriptions_keyword', 'notification_subscriptions', ['keyword'])

    # 创建推送记录表
    op.create_table(
        'notification_pushes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('subscription_id', sa.Integer(), nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='sent'),
        sa.Column('pushed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['subscription_id'], ['notification_subscriptions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notification_pushes_user_id', 'notification_pushes', ['user_id'])
    op.create_index('ix_notification_pushes_article_id', 'notification_pushes', ['article_id'])
    op.create_index('ix_notification_pushes_status', 'notification_pushes', ['status'])

    # 创建 Web Push 订阅表
    op.create_table(
        'web_push_subscriptions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('endpoint', sa.Text(), nullable=False),
        sa.Column('p256dh', sa.Text(), nullable=False),
        sa.Column('auth', sa.Text(), nullable=False),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'endpoint', name='uq_user_endpoint')
    )
    op.create_index('ix_web_push_subscriptions_user_id', 'web_push_subscriptions', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_web_push_subscriptions_user_id', table_name='web_push_subscriptions')
    op.drop_table('web_push_subscriptions')

    op.drop_index('ix_notification_pushes_status', table_name='notification_pushes')
    op.drop_index('ix_notification_pushes_article_id', table_name='notification_pushes')
    op.drop_index('ix_notification_pushes_user_id', table_name='notification_pushes')
    op.drop_table('notification_pushes')

    op.drop_index('ix_notification_subscriptions_keyword', table_name='notification_subscriptions')
    op.drop_index('ix_notification_subscriptions_target_id', table_name='notification_subscriptions')
    op.drop_index('ix_notification_subscriptions_user_id', table_name='notification_subscriptions')
    op.drop_table('notification_subscriptions')
