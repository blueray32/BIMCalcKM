"""add_price_item_id_to_items

Revision ID: d5e6f7g8h9i0
Revises: b2c3d4e5f6g7
Create Date: 2025-11-27 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d5e6f7g8h9i0"
down_revision: Union[str, None] = "b2c3d4e5f6g7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add price_item_id column to items table
    op.add_column(
        "items", sa.Column("price_item_id", sa.Uuid(as_uuid=True), nullable=True)
    )
    op.create_index(
        op.f("ix_items_price_item_id"), "items", ["price_item_id"], unique=False
    )


def downgrade() -> None:
    # Remove price_item_id column from items table
    op.drop_index(op.f("ix_items_price_item_id"), table_name="items")
    op.drop_column("items", "price_item_id")
