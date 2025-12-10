"""Add analysis_queries table for storing user query history.

Revision ID: 010
Revises: 009
Create Date: 2024-12-10 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '010'
down_revision: Union[str, None] = '009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建 analysis_queries 表
    op.create_table(
        'analysis_queries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # 创建索引
    op.create_index('idx_analysis_queries_user_id', 'analysis_queries', ['user_id'])
    op.create_index('idx_analysis_queries_created_at', 'analysis_queries', ['created_at'])


def downgrade() -> None:
    op.drop_index('idx_analysis_queries_created_at', table_name='analysis_queries')
    op.drop_index('idx_analysis_queries_user_id', table_name='analysis_queries')
    op.drop_table('analysis_queries')
