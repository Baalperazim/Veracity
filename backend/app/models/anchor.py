import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AnchorStatus(str, PyEnum):
    PREPARED = "prepared"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"


class AssetAnchor(Base):
    __tablename__ = "asset_anchors"
    __table_args__ = (
        UniqueConstraint("asset_id", name="uq_asset_anchors_asset_id"),
        UniqueConstraint("anchor_hash", name="uq_asset_anchors_anchor_hash"),
        UniqueConstraint("tx_hash", name="uq_asset_anchors_tx_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    asset_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("assets.id"), nullable=False)
    chain_id: Mapped[int] = mapped_column(nullable=False)
    registry_address: Mapped[str] = mapped_column(String(64), nullable=False)
    anchor_schema: Mapped[str] = mapped_column(String(64), nullable=False)
    anchor_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    anchor_payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[AnchorStatus] = mapped_column(
        Enum(AnchorStatus, name="anchor_status"), nullable=False, default=AnchorStatus.PREPARED
    )
    tx_hash: Mapped[str | None] = mapped_column(String(66), nullable=True)
    block_number: Mapped[int | None] = mapped_column(nullable=True)
    prepared_by: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    asset = relationship("Asset", back_populates="anchors")
