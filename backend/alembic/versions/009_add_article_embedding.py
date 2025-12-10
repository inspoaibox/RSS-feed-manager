"""Add embedding column to articles table for vector search.

Revision ID: 009
Revises: 008
Create Date: 2024-12-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009'
down_revision: Union[str, None] = '008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 启用 pgvector 扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    
    # 为 articles 表添加 embedding 向量列 (1536 维，OpenAI text-embedding-3-small)
    op.execute('ALTER TABLE articles ADD COLUMN embedding vector(1536)')
    
    # 创建向量索引（IVFFlat，适合中等规模数据）
    # 注意：需要先有一些数据才能创建 IVFFlat 索引，所以这里使用 HNSW 索引
    # HNSW 索引不需要预先有数据，且查询性能更好
    op.execute('''
        CREATE INDEX idx_articles_embedding 
        ON articles 
        USING hnsw (embedding vector_cosine_ops)
    ''')


def downgrade() -> None:
    # 删除向量索引
    op.execute('DROP INDEX IF EXISTS idx_articles_embedding')
    
    # 删除 embedding 列
    op.drop_column('articles', 'embedding')
    
    # 注意：不删除 pgvector 扩展，因为可能有其他表在使用
