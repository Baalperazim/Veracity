"""initial schema

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-03-10 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    asset_type = sa.Enum("land", "property", name="asset_type")
    verification_status = sa.Enum("pending", "under_review", "verified", "rejected", name="verification_status")
    decision_status = sa.Enum("open", "approved", "rejected", name="decision_status")

    asset_type.create(op.get_bind(), checkfirst=True)
    verification_status.create(op.get_bind(), checkfirst=True)
    decision_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "assets",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_type", asset_type, nullable=False),
        sa.Column("country_code", sa.String(length=2), nullable=False),
        sa.Column("state", sa.String(length=120), nullable=False),
        sa.Column("lga", sa.String(length=120), nullable=False),
        sa.Column("locality", sa.String(length=255), nullable=False),
        sa.Column("parcel_reference", sa.String(length=255), nullable=False),
        sa.Column("area_sqm", sa.String(length=64), nullable=False),
        sa.Column("owner_full_name", sa.String(length=255), nullable=False),
        sa.Column("owner_reference", sa.String(length=255), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("canonical_payload", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("current_status", verification_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_assets_fingerprint"),
    )

    op.create_table(
        "verification_cases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", decision_status, nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("rules_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "attestations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("verification_case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("attestation_type", sa.String(length=120), nullable=False),
        sa.Column("payload_hash", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["verification_case_id"], ["verification_cases.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "document_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=120), nullable=False),
        sa.Column("document_hash", sa.String(length=128), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("asset_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", sa.String(length=80), nullable=False),
        sa.Column("actor_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=120), nullable=False),
        sa.Column("event_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["asset_id"], ["assets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("document_records")
    op.drop_table("attestations")
    op.drop_table("verification_cases")
    op.drop_table("assets")

    sa.Enum(name="decision_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="verification_status").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="asset_type").drop(op.get_bind(), checkfirst=True)
