"""add customer balance columns

Revision ID: 002
Revises: 001
Create Date: 2026-03-15
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("customers", sa.Column("total_outstanding", sa.Float(), server_default="0"))
    op.add_column("customers", sa.Column("available_credit", sa.Float(), server_default="0"))


def downgrade() -> None:
    op.drop_column("customers", "available_credit")
    op.drop_column("customers", "total_outstanding")
