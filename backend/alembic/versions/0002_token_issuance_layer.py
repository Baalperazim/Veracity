"""token issuance execution layer

Revision ID: 0002_token_issuance_layer
Revises: 0001_initial_schema
Create Date: 2026-03-14 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_token_issuance_layer"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    issuance_stage = sa.Enum(
        "eligible_for_tokenization",
        "issuance_pending",
        "issuance_authorized",
        "token_minted",
        "issuance_completed",
        name="issuance_stage",
    )
    issuance_stage.create(op.get_bind(), checkfirst=True)

    op.add_column("assets", sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column(
        "assets", sa.Column("has_active_dispute", sa.Boolean(), nullable=False, server_default=sa.text("false"))
    )

    op.create_table(
        "token_issuances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stage", issuance_stage, nullable=False),
        sa.Column("minted_token_id", sa.String(length=255), nullable=True),
        sa.Column("onchain_anchor_reference", sa.String(length=255), nullable=True),
        sa.Column("onchain_anchor_payload", sa.JSON(), nullable=False),
        sa.Column("issuance_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
    )


def downgrade() -> None:
    op.drop_table("token_issuances")
    op.drop_column("assets", "has_active_dispute")
    op.drop_column("assets", "is_frozen")
    sa.Enum(name="issuance_stage").drop(op.get_bind(), checkfirst=True)
