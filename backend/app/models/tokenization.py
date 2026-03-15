import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enum_compat import StrEnum
from app.db.base import Base


class TokenizationModel(StrEnum):
    NFT_ONLY = "nft_only"
    DUAL_LAYER = "dual_layer"


class TransferRestrictionMode(StrEnum):
    OPEN = "open"
    WHITELIST_ONLY = "whitelist_only"
    JURISDICTION_LOCK = "jurisdiction_lock"


class IssuanceStatus(StrEnum):
    DRAFT = "draft"
    ELIGIBLE = "eligible"
    ISSUED = "issued"
    BLOCKED = "blocked"


class ComplianceBlockType(StrEnum):
    FREEZE = "freeze"
    DISPUTE = "dispute"
    REGULATORY_HOLD = "regulatory_hold"


class ComplianceBlockStatus(StrEnum):
    ACTIVE = "active"
    RELEASED = "released"


class TokenizationPolicy(Base):
    __tablename__ = "tokenization_policies"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, unique=True)
    tokenization_model: Mapped[TokenizationModel] = mapped_column(
        Enum(TokenizationModel, name="tokenization_model"), nullable=False, default=TokenizationModel.DUAL_LAYER
    )
    allows_fractionalization: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_verification_status: Mapped[str] = mapped_column(String(40), nullable=False, default="verified")
    requires_manual_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    transfer_restriction_mode: Mapped[TransferRestrictionMode] = mapped_column(
        Enum(TransferRestrictionMode, name="transfer_restriction_mode"),
        nullable=False,
        default=TransferRestrictionMode.WHITELIST_ONLY,
    )
    allowed_jurisdictions: Mapped[list[str]] = mapped_column(JSON, default=list)
    whitelisted_wallets: Mapped[list[str]] = mapped_column(JSON, default=list)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    asset = relationship("Asset", back_populates="tokenization_policy")


class TokenizationIssuance(Base):
    __tablename__ = "tokenization_issuances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, unique=True)
    policy_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tokenization_policies.id"), nullable=False)
    status: Mapped[IssuanceStatus] = mapped_column(
        Enum(IssuanceStatus, name="issuance_status"), nullable=False, default=IssuanceStatus.DRAFT
    )
    identity_contract: Mapped[str | None] = mapped_column(String(255), nullable=True)
    identity_token_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fractional_contract: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fractional_token_class: Mapped[str | None] = mapped_column(String(120), nullable=True)
    fractional_total_supply: Mapped[int | None] = mapped_column(Integer, nullable=True)
    issuance_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    eligibility_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    asset = relationship("Asset", back_populates="tokenization_issuance")
    policy = relationship("TokenizationPolicy")


class AssetComplianceBlock(Base):
    __tablename__ = "asset_compliance_blocks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    block_type: Mapped[ComplianceBlockType] = mapped_column(
        Enum(ComplianceBlockType, name="compliance_block_type"), nullable=False
    )
    status: Mapped[ComplianceBlockStatus] = mapped_column(
        Enum(ComplianceBlockStatus, name="compliance_block_status"),
        nullable=False,
        default=ComplianceBlockStatus.ACTIVE,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(120), nullable=False)
    released_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asset = relationship("Asset", back_populates="compliance_blocks")
