def test_register_asset_creates_verification_case_and_returns_fingerprint(client) -> None:
    payload = {
        "asset_type": "land",
        "country_code": "NG",
        "state": "Lagos",
        "lga": "Ikeja",
        "locality": "Alausa",
        "parcel_reference": "IKJ-PLT-8",
        "area_sqm": "450",
        "owner_full_name": "Amina Yusuf",
        "owner_reference": "NIN-0099",
        "metadata": {"title_number": "LND-23"},
        "submitted_by": "owner_amina",
    }

    response = client.post("/api/v1/assets", json=payload)
    assert response.status_code == 201

    body = response.json()
    assert len(body["fingerprint"]) == 64
    assert body["current_status"] == "pending"
    assert body["verification_case_id"]


def test_register_asset_rejects_duplicate_fingerprint(client) -> None:
    payload = {
        "asset_type": "land",
        "country_code": "NG",
        "state": "Kaduna",
        "lga": "Chikun",
        "locality": "Nasarawa",
        "parcel_reference": "KD-1133",
        "area_sqm": "600sqm",
        "owner_full_name": "Tunde Bello",
        "owner_reference": "NIN-7731",
        "metadata": {},
        "submitted_by": "owner_tunde",
    }

    first = client.post("/api/v1/assets", json=payload)
    assert first.status_code == 201

    duplicate_variant = payload | {
        "state": " KADUNA ",
        "lga": "chikun",
        "locality": "nasarawa",
        "area_sqm": "600",
        "owner_full_name": "tunde bello",
        "owner_reference": "nin-7731",
    }
    second = client.post("/api/v1/assets", json=duplicate_variant)

    assert second.status_code == 409
    assert "canonical fingerprint" in second.json()["detail"]
