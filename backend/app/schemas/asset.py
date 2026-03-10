from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.anchor import AnchorStatus
from app.models.asset import AssetType, VerificationStatus


class AssetRegistrationRequest(BaseModel):
    asset_type: AssetType
    country_code: str = Field(min_length=2, max_length=2, description="ISO country code")
    state: str = Field(min_length=2, max_length=120)
    lga: str = Field(min_length=2, max_length=120)
    locality: str = Field(min_length=2, max_length=255)
    parcel_reference: str = Field(min_length=2, max_length=255)
    area_sqm: str = Field(min_length=1, max_length=64)
    owner_full_name: str = Field(min_length=3, max_length=255)
    owner_reference: str = Field(min_length=3, max_length=255)
    metadata: dict = Field(default_factory=dict)
    submitted_by: str = Field(min_length=2, max_length=120)


class AssetRegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fingerprint: str
    current_status: VerificationStatus
    verification_case_id: UUID
    created_at: datetime


class AnchorPreparationRequest(BaseModel):
    chain_id: int = Field(gt=0)
    registry_address: str = Field(min_length=42, max_length=64)
    prepared_by: str = Field(min_length=2, max_length=120)


class AnchorPreparationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    anchor_id: UUID
    asset_id: UUID
    chain_id: int
    registry_address: str
    anchor_hash: str
    anchor_schema: str
    status: AnchorStatus
    created_at: datetime


class AnchorRecordRequest(BaseModel):
    tx_hash: str = Field(min_length=66, max_length=66)
    block_number: int = Field(gt=0)


class AnchorRecordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    anchor_id: UUID
    asset_id: UUID
    status: AnchorStatus
    tx_hash: str
    block_number: int
    updated_at: datetime
