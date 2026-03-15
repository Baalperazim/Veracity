import uuid
from datetime import datetime
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class IssuanceStage(str, enum.Enum):
    ELIGIBLE_FOR_TOKENIZATION = "eligible_for_tokenization"
    ISSUANCE_PENDING = "issuance_pending"
    ISSUANCE_AUTHORIZED = "issuance_authorized"
    TOKEN_MINTED = "token_minted"
    ISSUANCE_COMPLETED = "issuance_completed"


class TokenIssuance(Base):
    __tablename__ = "token_issuances"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False, unique=True)
    stage: Mapped[IssuanceStage] = mapped_column(
        Enum(IssuanceStage, name="issuance_stage"),
        nullable=False,
        default=IssuanceStage.ELIGIBLE_FOR_TOKENIZATION,
    )
    minted_token_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onchain_anchor_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    onchain_anchor_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    issuance_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    asset = relationship("Asset", back_populates="issuance")
