from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.tokenization import (
    ComplianceBlockType,
    IssuanceStatus,
    TokenizationModel,
    TransferRestrictionMode,
)


class TokenizationPolicyInput(BaseModel):
    tokenization_model: TokenizationModel = TokenizationModel.DUAL_LAYER
    allows_fractionalization: bool = True
    min_verification_status: str = Field(default="verified", min_length=3, max_length=40)
    requires_manual_approval: bool = True
    transfer_restriction_mode: TransferRestrictionMode = TransferRestrictionMode.WHITELIST_ONLY
    allowed_jurisdictions: list[str] = Field(default_factory=list)
    whitelisted_wallets: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


class TokenizationIssueRequest(BaseModel):
    policy: TokenizationPolicyInput = Field(default_factory=TokenizationPolicyInput)
    requested_by: str = Field(min_length=2, max_length=120)
    manual_approved: bool = False
    identity_contract: str = Field(min_length=2, max_length=255)
    identity_token_id: str = Field(min_length=1, max_length=120)
    fractional_contract: str | None = Field(default=None, min_length=2, max_length=255)
    fractional_token_class: str | None = Field(default=None, min_length=1, max_length=120)
    fractional_total_supply: int | None = Field(default=None, ge=1)
    issuance_reference: str | None = Field(default=None, min_length=2, max_length=255)


class TokenizationIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asset_id: UUID
    issuance_id: UUID
    status: IssuanceStatus
    tokenization_model: TokenizationModel
    transfer_restriction_mode: TransferRestrictionMode
    eligibility_snapshot: dict
    issued_at: datetime


class ComplianceBlockCreateRequest(BaseModel):
    block_type: ComplianceBlockType
    reason: str = Field(min_length=3)
    created_by: str = Field(min_length=2, max_length=120)
    metadata: dict = Field(default_factory=dict)


class ComplianceBlockResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    block_id: UUID
    asset_id: UUID
    block_type: ComplianceBlockType
    status: str
    reason: str
