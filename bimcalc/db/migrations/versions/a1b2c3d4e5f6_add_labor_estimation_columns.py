"""Add labor estimation columns

Revision ID: a1b2c3d4e5f6
Revises: 3314906526e2
Create Date: 2025-11-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = ("3314906526e2", "c49e4d2570ce")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add labor columns to price_items
    op.add_column(
        "price_items",
        sa.Column("labor_hours", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column("price_items", sa.Column("labor_code", sa.Text(), nullable=True))
    op.create_index(
        op.f("ix_price_items_labor_code"), "price_items", ["labor_code"], unique=False
    )

    # Add source and confidence_score to item_mapping
    op.add_column("item_mapping", sa.Column("source", sa.Text(), nullable=True))
    op.add_column(
        "item_mapping",
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=True),
    )


def downgrade() -> None:
    # Remove columns from item_mapping
    op.drop_column("item_mapping", "confidence_score")
    op.drop_column("item_mapping", "source")

    # Remove columns from price_items
    op.drop_index(op.f("ix_price_items_labor_code"), table_name="price_items")
    op.drop_column("price_items", "labor_code")
    op.drop_column("price_items", "labor_hours")
