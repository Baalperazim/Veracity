from pathlib import Path

from app.blockchain import ASSET_REGISTRY_EVENT_SIGNATURE, ASSET_REGISTRY_FUNCTION_SIGNATURE
from app.services.anchoring import build_anchor_hash


def _create_asset(client):
    payload = {
        "asset_type": "land",
        "country_code": "NG",
        "state": "Lagos",
        "lga": "Ikeja",
        "locality": "Alausa",
        "parcel_reference": "IKJ-ANCHOR-1",
        "area_sqm": "500",
        "owner_full_name": "Anchor Owner",
        "owner_reference": "NIN-ANCHOR-100",
        "metadata": {"title_number": "ANCHOR-001"},
        "submitted_by": "anchor_owner",
    }
    response = client.post("/api/v1/assets", json=payload)
    assert response.status_code == 201
    return response.json()


def test_prepare_anchor_and_record_onchain_submission(client) -> None:
    asset = _create_asset(client)

    prepare = client.post(
        f"/api/v1/assets/{asset['id']}/anchors/prepare",
        json={
            "chain_id": 11155111,
            "registry_address": "0x1234567890abcdef1234567890abcdef12345678",
            "prepared_by": "system_anchor_worker",
        },
    )
    assert prepare.status_code == 201
    prepared_body = prepare.json()
    assert prepared_body["status"] == "prepared"
    assert len(prepared_body["anchor_hash"]) == 64

    record = client.post(
        f"/api/v1/assets/{asset['id']}/anchors/{prepared_body['anchor_id']}/record",
        json={
            "tx_hash": "0x" + "a" * 64,
            "block_number": 555,
        },
    )
    assert record.status_code == 200
    record_body = record.json()
    assert record_body["status"] == "submitted"
    assert record_body["tx_hash"] == "0x" + "a" * 64


def test_anchor_hash_deterministic_for_same_payload() -> None:
    payload = {
        "schema": "asset_anchor_v1",
        "asset_id": "11111111-1111-1111-1111-111111111111",
        "fingerprint": "b" * 64,
        "canonical_payload": {"a": 1, "b": "2"},
    }

    hash_a = build_anchor_hash(payload)
    hash_b = build_anchor_hash(payload)

    assert hash_a == hash_b
    assert len(hash_a) == 64


def test_contract_and_backend_signature_assumptions_stay_aligned() -> None:
    contract_source = Path(__file__).resolve().parents[2] / "contracts" / "src" / "AssetRegistry.sol"
    source_text = contract_source.read_text()

    assert ASSET_REGISTRY_FUNCTION_SIGNATURE in source_text
    assert ASSET_REGISTRY_EVENT_SIGNATURE in source_text


def test_prepare_anchor_rejects_invalid_registry_address(client) -> None:
    asset = _create_asset(client)

    prepare = client.post(
        f"/api/v1/assets/{asset['id']}/anchors/prepare",
        json={
            "chain_id": 11155111,
            "registry_address": "registry-address",
            "prepared_by": "system_anchor_worker",
        },
    )
    assert prepare.status_code == 422
