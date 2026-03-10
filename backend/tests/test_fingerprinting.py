import pytest

from app.models.asset import AssetType
from app.schemas.asset import AssetRegistrationRequest
from app.services.fingerprinting import build_canonical_asset_payload, generate_asset_fingerprint


def test_fingerprint_is_deterministic_despite_whitespace_and_case() -> None:
    payload_a = AssetRegistrationRequest(
        asset_type=AssetType.LAND,
        country_code="ng",
        state="  Oyo State",
        lga="ibadan north  ",
        locality="  bodija Extension",
        parcel_reference="  PLT-994-XY ",
        area_sqm="500 sqm",
        owner_full_name=" Adaeze Nwosu ",
        owner_reference="NIN-111-22",
        metadata={"survey_plan": "abc"},
        submitted_by="owner_01",
    )
    payload_b = AssetRegistrationRequest(
        asset_type=AssetType.LAND,
        country_code="NG",
        state="oyo state",
        lga="IBADAN NORTH",
        locality="BODIJA   extension",
        parcel_reference="plt-994-xy",
        area_sqm="500",
        owner_full_name="adaeze nwosu",
        owner_reference="nin-111-22",
        metadata={"survey_plan": "def"},
        submitted_by="owner_01",
    )

    fp_a = generate_asset_fingerprint(build_canonical_asset_payload(payload_a))
    fp_b = generate_asset_fingerprint(build_canonical_asset_payload(payload_b))

    assert fp_a == fp_b


def test_area_must_be_positive() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        AssetRegistrationRequest(
            asset_type=AssetType.LAND,
            country_code="NG",
            state="Lagos",
            lga="Ikeja",
            locality="Alausa",
            parcel_reference="IKJ-PLT-8",
            area_sqm="0",
            owner_full_name="Amina Yusuf",
            owner_reference="NIN-0099",
            metadata={},
            submitted_by="owner_amina",
        )


def test_country_code_must_be_two_letters() -> None:
    with pytest.raises(ValueError, match="2-letter ISO"):
        AssetRegistrationRequest(
            asset_type=AssetType.LAND,
            country_code="N1",
            state="Lagos",
            lga="Ikeja",
            locality="Alausa",
            parcel_reference="IKJ-PLT-8",
            area_sqm="450",
            owner_full_name="Amina Yusuf",
            owner_reference="NIN-0099",
            metadata={},
            submitted_by="owner_amina",
        )
