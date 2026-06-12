"""Add unique constraint to ai_models table.

Revision ID: 014
Revises: 013
Create Date: 2025-12-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '014'
down_revision: Union[str, None] = '013'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # First, remove duplicate models (keep the first one by id)
    conn = op.get_bind()
    
    # Find and delete duplicates
    conn.execute(sa.text("""
        DELETE FROM ai_models 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM ai_models 
            GROUP BY provider_id, model_id
        )
    """))
    
    # Add unique constraint
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('ai_models') as batch_op:
            batch_op.create_unique_constraint(
                'uq_ai_models_provider_model',
                ['provider_id', 'model_id'],
            )
    else:
        op.create_unique_constraint(
            'uq_ai_models_provider_model',
            'ai_models',
            ['provider_id', 'model_id']
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == 'sqlite':
        with op.batch_alter_table('ai_models') as batch_op:
            batch_op.drop_constraint('uq_ai_models_provider_model', type_='unique')
    else:
        op.drop_constraint('uq_ai_models_provider_model', 'ai_models', type_='unique')
