import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, JSON, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class VerificationCaseStatus(str, enum.Enum):
    OPEN = "open"
    UNDER_REVIEW = "under_review"
    CONFLICTED = "conflicted"
    APPROVED = "approved"
    REJECTED = "rejected"
    ISSUANCE_READY = "issuance_ready"
    ISSUED = "issued"


class VerifierRole(str, enum.Enum):
    LAND_REGISTRY_OFFICER = "land_registry_officer"
    LICENSED_SURVEYOR = "licensed_surveyor"
    LEGAL_REVIEWER = "legal_reviewer"


class VerificationCase(Base):
    __tablename__ = "verification_cases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    status: Mapped[VerificationCaseStatus] = mapped_column(
        Enum(VerificationCaseStatus, name="verification_case_status"),
        nullable=False,
        default=VerificationCaseStatus.OPEN,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rules_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    asset = relationship("Asset", back_populates="verification_cases")
    attestations = relationship("Attestation", back_populates="verification_case", cascade="all, delete-orphan")


class Attestation(Base):
    __tablename__ = "attestations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    verification_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("verification_cases.id"), nullable=False
    )
    verifier_role: Mapped[VerifierRole | None] = mapped_column(
        Enum(VerifierRole, name="verifier_role"),
        nullable=True,
    )
    verifier_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    attestation_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    is_revoked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    verification_case = relationship("VerificationCase", back_populates="attestations")
