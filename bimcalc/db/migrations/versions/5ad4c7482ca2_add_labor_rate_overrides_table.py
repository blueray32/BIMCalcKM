"""add_labor_rate_overrides_table

Revision ID: 5ad4c7482ca2
Revises: d5e6f7g8h9i0
Create Date: 2025-11-27 14:20:21.826468

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5ad4c7482ca2'
down_revision: Union[str, None] = 'd5e6f7g8h9i0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create labor_rate_overrides table
    op.create_table(
        'labor_rate_overrides',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', sa.dialects.postgresql.UUID(as_uuid=True), 
                  sa.ForeignKey('projects.id', ondelete='CASCADE'), 
                  nullable=False),
        sa.Column('category', sa.Text, nullable=False),
        sa.Column('rate', sa.Numeric(10, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        
        # Unique constraint: one rate per (project, category)
        sa.UniqueConstraint('project_id', 'category', name='uq_project_category_rate')
    )
    
    # Create indexes
    op.create_index('idx_labor_rate_project', 'labor_rate_overrides', ['project_id'])


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_labor_rate_project', table_name='labor_rate_overrides')
    
    # Drop table
    op.drop_table('labor_rate_overrides')
