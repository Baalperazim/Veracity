from uuid import UUID

from app.models.asset import Asset, VerificationStatus


def _register_asset(client):
    payload = {
        "asset_type": "land",
        "country_code": "NG",
        "state": "Lagos",
        "lga": "Ikeja",
        "locality": "Alausa",
        "parcel_reference": "IKJ-PLT-11",
        "area_sqm": "1000",
        "owner_full_name": "Ifeoma Okafor",
        "owner_reference": "NIN-4551",
        "metadata": {"title_number": "LOS-881"},
        "submitted_by": "owner_ifeoma",
    }
    response = client.post("/api/v1/assets", json=payload)
    assert response.status_code == 201
    return UUID(response.json()["id"])


def test_tokenization_issue_requires_verified_and_manual_approval(client, test_session):
    asset_id = _register_asset(client)

    issue_payload = {
        "policy": {
            "tokenization_model": "dual_layer",
            "requires_manual_approval": True,
            "allows_fractionalization": True,
            "transfer_restriction_mode": "whitelist_only",
            "whitelisted_wallets": ["0xabc"],
        },
        "requested_by": "compliance_admin",
        "manual_approved": False,
        "identity_contract": "0xidentity",
        "identity_token_id": "1",
        "fractional_contract": "0xfractional",
        "fractional_token_class": "A",
        "fractional_total_supply": 1000,
    }

    blocked = client.post(f"/api/v1/assets/{asset_id}/tokenization/issue", json=issue_payload)
    assert blocked.status_code == 409

    asset = test_session.get(Asset, asset_id)
    asset.current_status = VerificationStatus.VERIFIED
    test_session.commit()

    issue_payload["manual_approved"] = True
    allowed = client.post(f"/api/v1/assets/{asset_id}/tokenization/issue", json=issue_payload)
    assert allowed.status_code == 200
    body = allowed.json()
    assert body["status"] == "issued"
    assert body["tokenization_model"] == "dual_layer"
    assert body["transfer_restriction_mode"] == "whitelist_only"


def test_freeze_block_prevents_token_issuance(client, test_session):
    asset_id = _register_asset(client)

    asset = test_session.get(Asset, asset_id)
    asset.current_status = VerificationStatus.VERIFIED
    test_session.commit()

    block_payload = {
        "block_type": "freeze",
        "reason": "Court injunction pending title review",
        "created_by": "legal_officer",
        "metadata": {"case_id": "LAG-2026-77"},
    }
    block_response = client.post(f"/api/v1/assets/{asset_id}/tokenization/blocks", json=block_payload)
    assert block_response.status_code == 201

    issue_payload = {
        "policy": {
            "tokenization_model": "dual_layer",
            "requires_manual_approval": False,
            "allows_fractionalization": True,
            "transfer_restriction_mode": "jurisdiction_lock",
            "allowed_jurisdictions": ["NG"],
        },
        "requested_by": "tokenization_bot",
        "manual_approved": False,
        "identity_contract": "0xidentity2",
        "identity_token_id": "11",
        "fractional_contract": "0xfractional2",
        "fractional_token_class": "A",
        "fractional_total_supply": 500,
    }
    issuance = client.post(f"/api/v1/assets/{asset_id}/tokenization/issue", json=issue_payload)
    assert issuance.status_code == 409
