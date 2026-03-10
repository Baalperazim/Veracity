from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.audit import AuditEvent
from app.models.verification import VerificationCase
from app.schemas.asset import AssetRegistrationRequest
from app.services.fingerprinting import build_canonical_asset_payload, generate_asset_fingerprint


class DuplicateAssetError(Exception):
    pass


def register_asset(db: Session, payload: AssetRegistrationRequest) -> tuple[Asset, VerificationCase]:
    canonical_payload = build_canonical_asset_payload(payload)
    fingerprint = generate_asset_fingerprint(canonical_payload)

    existing = db.scalar(select(Asset).where(Asset.fingerprint == fingerprint))
    if existing:
        raise DuplicateAssetError("An asset with this canonical fingerprint already exists")

    asset = Asset(
        asset_type=payload.asset_type,
        country_code=payload.country_code,
        state=payload.state,
        lga=payload.lga,
        locality=payload.locality,
        parcel_reference=payload.parcel_reference,
        area_sqm=payload.area_sqm,
        owner_full_name=payload.owner_full_name,
        owner_reference=payload.owner_reference,
        metadata_json=payload.metadata,
        fingerprint=fingerprint,
        canonical_payload=canonical_payload,
    )
    db.add(asset)
    db.flush()

    verification_case = VerificationCase(asset_id=asset.id, rules_snapshot={"version": "v1", "name": "base_registration"})
    db.add(verification_case)

    audit_event = AuditEvent(
        asset_id=asset.id,
        actor_role="owner",
        actor_id=payload.submitted_by,
        event_type="asset.registration_submitted",
        event_payload={"fingerprint": fingerprint},
    )
    db.add(audit_event)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateAssetError("An asset with this canonical fingerprint already exists") from exc
    db.refresh(asset)
    db.refresh(verification_case)

    return asset, verification_case
