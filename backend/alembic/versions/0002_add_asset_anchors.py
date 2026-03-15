"""add asset anchors

Revision ID: 0002_add_asset_anchors
Revises: 0001_initial_schema
Create Date: 2026-03-10 00:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_add_asset_anchors"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    anchor_status = sa.Enum("prepared", "submitted", "confirmed", name="anchor_status")
    anchor_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "asset_anchors",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chain_id", sa.Integer(), nullable=False),
        sa.Column("registry_address", sa.String(length=64), nullable=False),
        sa.Column("anchor_schema", sa.String(length=64), nullable=False),
        sa.Column("anchor_hash", sa.String(length=64), nullable=False),
        sa.Column("anchor_payload", sa.JSON(), nullable=False),
        sa.Column("status", anchor_status, nullable=False),
        sa.Column("tx_hash", sa.String(length=66), nullable=True),
        sa.Column("block_number", sa.Integer(), nullable=True),
        sa.Column("prepared_by", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("anchor_hash", name="uq_asset_anchors_anchor_hash"),
        sa.UniqueConstraint("asset_id", name="uq_asset_anchors_asset_id"),
        sa.UniqueConstraint("tx_hash", name="uq_asset_anchors_tx_hash"),
    )


def downgrade() -> None:
    op.drop_table("asset_anchors")
    sa.Enum(name="anchor_status").drop(op.get_bind(), checkfirst=True)
