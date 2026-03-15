import uuid
from datetime import datetime
from enum import Enum as PyEnum
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssetType(str, PyEnum):
class AssetType(str, enum.Enum):
    LAND = "land"
    PROPERTY = "property"


class VerificationStatus(str, PyEnum):
class VerificationStatus(str, enum.Enum):
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (UniqueConstraint("fingerprint", name="uq_assets_fingerprint"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType, name="asset_type"), nullable=False)
    country_code: Mapped[str] = mapped_column(String(2), nullable=False)
    state: Mapped[str] = mapped_column(String(120), nullable=False)
    lga: Mapped[str] = mapped_column(String(120), nullable=False)
    locality: Mapped[str] = mapped_column(String(255), nullable=False)
    parcel_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    area_sqm: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_reference: Mapped[str] = mapped_column(String(255), nullable=False)
    fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    canonical_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    asset_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    current_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"),
        nullable=False,
        default=VerificationStatus.PENDING,
    )
    is_frozen: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    has_active_dispute: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    verification_cases = relationship("VerificationCase", back_populates="asset", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="asset", cascade="all, delete-orphan")
    documents = relationship("DocumentRecord", back_populates="asset", cascade="all, delete-orphan")
    anchors = relationship("AssetAnchor", back_populates="asset", cascade="all, delete-orphan")
    issuance = relationship("TokenIssuance", back_populates="asset", uselist=False, cascade="all, delete-orphan")


class DocumentRecord(Base):
    __tablename__ = "document_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    document_type: Mapped[str] = mapped_column(String(120), nullable=False)
    document_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    document_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    asset = relationship("Asset", back_populates="documents")
