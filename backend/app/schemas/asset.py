from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    metadata: dict[str, Any] = Field(default_factory=dict)
    submitted_by: str = Field(min_length=2, max_length=120)

    @field_validator("country_code")
    @classmethod
    def validate_country_code(cls, value: str) -> str:
        normalized = value.strip().upper()
        if len(normalized) != 2 or not normalized.isalpha():
            raise ValueError("country_code must be a 2-letter ISO code")
        return normalized

    @field_validator(
        "state",
        "lga",
        "locality",
        "parcel_reference",
        "owner_full_name",
        "owner_reference",
        "submitted_by",
    )
    @classmethod
    def strip_and_require_non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be blank")
        return normalized

    @field_validator("area_sqm")
    @classmethod
    def validate_area_sqm(cls, value: str) -> str:
        compact = value.strip().lower().replace(" ", "")
        if compact.endswith("sqm"):
            compact = compact[:-3]
        try:
            area = Decimal(compact)
        except InvalidOperation as exc:
            raise ValueError("area_sqm must be numeric or numeric with sqm suffix") from exc
        if area <= 0:
            raise ValueError("area_sqm must be greater than zero")
        return value.strip()

    @field_validator("metadata")
    @classmethod
    def validate_metadata_size(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 50:
            raise ValueError("metadata cannot contain more than 50 keys")
        return value


class AssetRegistrationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    fingerprint: str
    current_status: VerificationStatus
    verification_case_id: UUID
    created_at: datetime
