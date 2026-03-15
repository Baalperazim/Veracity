import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.blockchain import ASSET_REGISTRY_SCHEMA_VERSION
from app.models.anchor import AnchorStatus, AssetAnchor
from app.models.asset import Asset
from app.schemas.asset import AnchorPreparationRequest, AnchorRecordRequest


class AssetNotFoundError(Exception):
    pass


class AnchorAlreadyExistsError(Exception):
    pass


class AnchorNotFoundError(Exception):
    pass


class AnchorStateError(Exception):
    pass


def build_anchor_payload(asset: Asset, schema: str = ASSET_REGISTRY_SCHEMA_VERSION) -> dict:
    return {
        "schema": schema,
        "asset_id": str(asset.id),
        "fingerprint": asset.fingerprint,
        "canonical_payload": asset.canonical_payload,
    }


def build_anchor_hash(anchor_payload: dict) -> str:
    canonical = json.dumps(anchor_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prepare_anchor(db: Session, asset_id: UUID, payload: AnchorPreparationRequest) -> AssetAnchor:
    asset = db.scalar(select(Asset).where(Asset.id == asset_id))
    if not asset:
        raise AssetNotFoundError("Asset not found")

    existing = db.scalar(select(AssetAnchor).where(AssetAnchor.asset_id == asset_id))
    if existing:
        raise AnchorAlreadyExistsError("Anchor already exists for this asset")

    anchor_payload = build_anchor_payload(asset)
    anchor_hash = build_anchor_hash(anchor_payload)

    anchor = AssetAnchor(
        asset_id=asset.id,
        chain_id=payload.chain_id,
        registry_address=payload.registry_address.lower(),
        anchor_schema=anchor_payload["schema"],
        anchor_hash=anchor_hash,
        anchor_payload=anchor_payload,
        status=AnchorStatus.PREPARED,
        prepared_by=payload.prepared_by,
    )
    db.add(anchor)
    db.commit()
    db.refresh(anchor)
    return anchor


def record_submitted_anchor(db: Session, asset_id: UUID, anchor_id: UUID, payload: AnchorRecordRequest) -> AssetAnchor:
    anchor = db.scalar(select(AssetAnchor).where(AssetAnchor.id == anchor_id, AssetAnchor.asset_id == asset_id))
    if not anchor:
        raise AnchorNotFoundError("Anchor not found")
    if anchor.status != AnchorStatus.PREPARED:
        raise AnchorStateError("Only prepared anchors can be recorded onchain")

    anchor.tx_hash = payload.tx_hash.lower()
    anchor.block_number = payload.block_number
    anchor.status = AnchorStatus.SUBMITTED
    db.commit()
    db.refresh(anchor)
    return anchor
