import hashlib
import json
from decimal import Decimal, InvalidOperation

from app.schemas.asset import AssetRegistrationRequest


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _normalize_area(value: str) -> str:
    compact = value.strip().lower().replace(" ", "")
    if compact.endswith("sqm"):
        compact = compact[:-3]
    try:
        normalized = Decimal(compact)
    except InvalidOperation as exc:
        raise ValueError("area_sqm must be numeric or numeric with sqm suffix") from exc
    return str(normalized.normalize())


def build_canonical_asset_payload(payload: AssetRegistrationRequest) -> dict:
    return {
        "asset_type": payload.asset_type.value,
        "country_code": payload.country_code.upper(),
        "state": _normalize_text(payload.state),
        "lga": _normalize_text(payload.lga),
        "locality": _normalize_text(payload.locality),
        "parcel_reference": _normalize_text(payload.parcel_reference),
        "area_sqm": _normalize_area(payload.area_sqm),
        "owner_full_name": _normalize_text(payload.owner_full_name),
        "owner_reference": _normalize_text(payload.owner_reference),
    }


def generate_asset_fingerprint(canonical_payload: dict) -> str:
    serialized = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
