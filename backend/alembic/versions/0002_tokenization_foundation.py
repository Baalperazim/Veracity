"""tokenization foundation

Revision ID: 0002_tokenization_foundation
Revises: 0001_initial_schema
Create Date: 2026-03-10 00:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_tokenization_foundation"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    tokenization_model = sa.Enum("nft_only", "dual_layer", name="tokenization_model")
    transfer_restriction_mode = sa.Enum(
        "open", "whitelist_only", "jurisdiction_lock", name="transfer_restriction_mode"
    )
    issuance_status = sa.Enum("draft", "eligible", "issued", "blocked", name="issuance_status")
    compliance_block_type = sa.Enum("freeze", "dispute", "regulatory_hold", name="compliance_block_type")
    compliance_block_status = sa.Enum("active", "released", name="compliance_block_status")

    tokenization_model.create(op.get_bind(), checkfirst=True)
    transfer_restriction_mode.create(op.get_bind(), checkfirst=True)
    issuance_status.create(op.get_bind(), checkfirst=True)
    compliance_block_type.create(op.get_bind(), checkfirst=True)
    compliance_block_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tokenization_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tokenization_model", tokenization_model, nullable=False),
        sa.Column("allows_fractionalization", sa.Boolean(), nullable=False),
        sa.Column("min_verification_status", sa.String(length=40), nullable=False),
        sa.Column("requires_manual_approval", sa.Boolean(), nullable=False),
        sa.Column("transfer_restriction_mode", transfer_restriction_mode, nullable=False),
        sa.Column("allowed_jurisdictions", sa.JSON(), nullable=False),
        sa.Column("whitelisted_wallets", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
    )

    op.create_table(
        "tokenization_issuances",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", issuance_status, nullable=False),
        sa.Column("identity_contract", sa.String(length=255), nullable=True),
        sa.Column("identity_token_id", sa.String(length=120), nullable=True),
        sa.Column("fractional_contract", sa.String(length=255), nullable=True),
        sa.Column("fractional_token_class", sa.String(length=120), nullable=True),
        sa.Column("fractional_total_supply", sa.Integer(), nullable=True),
        sa.Column("issuance_reference", sa.String(length=255), nullable=True),
        sa.Column("eligibility_snapshot", sa.JSON(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["policy_id"], ["tokenization_policies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("asset_id"),
    )

    op.create_table(
        "asset_compliance_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("block_type", compliance_block_type, nullable=False),
        sa.Column("status", compliance_block_status, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=False),
        sa.Column("released_by", sa.String(length=120), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("asset_compliance_blocks")
    op.drop_table("tokenization_issuances")
    op.drop_table("tokenization_policies")

    sa.Enum(name="compliance_block_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="compliance_block_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="issuance_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="transfer_restriction_mode").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="tokenization_model").drop(op.get_bind(), checkfirst=True)
