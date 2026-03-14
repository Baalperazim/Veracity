from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetType, VerificationStatus
from app.models.audit import AuditEvent
from app.models.issuance import IssuanceStage, TokenIssuance
from app.models.verification import Attestation, VerificationCase
from app.services.issuance import (
    BlockchainMintResult,
    EligibilityError,
    InvalidIssuanceTransition,
    IssuanceEligibilityGate,
    IssuanceService,
    OnchainAnchorRequest,
)


class StubBlockchainGateway:
    def mint_asset_token(self, request: OnchainAnchorRequest) -> BlockchainMintResult:
        assert request.asset_fingerprint
        assert request.registry_record_reference.startswith("asset:")
        return BlockchainMintResult(token_id="token-1001", anchor_reference="anchor://tx-501")


def _create_verified_asset(test_session: Session) -> tuple[Asset, VerificationCase]:
    asset = Asset(
        asset_type=AssetType.LAND,
        country_code="NG",
        state="Lagos",
        lga="Ikeja",
        locality="Alausa",
        parcel_reference=f"IKJ-{uuid4()}",
        area_sqm="100",
        owner_full_name="Amina Yusuf",
        owner_reference="NIN-0099",
        fingerprint=uuid4().hex + uuid4().hex,
        canonical_payload={"k": "v"},
        asset_metadata={},
        current_status=VerificationStatus.VERIFIED,
    )
    test_session.add(asset)
    test_session.flush()

    case = VerificationCase(
        asset_id=asset.id,
        rules_snapshot={
            "required_attestations": ["title_validation", "owner_identity"],
            "tokenization_policy": {"satisfied": True},
        },
    )
    test_session.add(case)
    test_session.flush()

    test_session.add_all(
        [
            Attestation(
                verification_case_id=case.id,
                provider="registry",
                attestation_type="title_validation",
                payload_hash="h1",
                payload={"ok": True},
            ),
            Attestation(
                verification_case_id=case.id,
                provider="idp",
                attestation_type="owner_identity",
                payload_hash="h2",
                payload={"ok": True},
            ),
        ]
    )
    test_session.commit()
    test_session.refresh(asset)
    test_session.refresh(case)
    return asset, case


def test_successful_issuance_flow(test_session: Session) -> None:
    asset, _ = _create_verified_asset(test_session)
    service = IssuanceService(test_session, StubBlockchainGateway())

    issuance = service.initiate_issuance(
        asset_id=asset.id,
        actor_id="ops-1",
        actor_role="operations",
        issuance_metadata={"batch_id": "B-100"},
    )

    assert issuance.stage == IssuanceStage.ISSUANCE_COMPLETED
    assert issuance.minted_token_id == "token-1001"
    assert issuance.onchain_anchor_reference == "anchor://tx-501"
    assert issuance.onchain_anchor_payload["asset_fingerprint"] == asset.fingerprint

    event_types = test_session.scalars(select(AuditEvent.event_type).where(AuditEvent.asset_id == asset.id)).all()
    assert "issuance.requested" in event_types
    assert "issuance.authorized" in event_types
    assert "issuance.token_minted" in event_types
    assert "issuance.completed" in event_types


def test_blocked_issuance_due_to_dispute(test_session: Session) -> None:
    asset, _ = _create_verified_asset(test_session)
    asset.has_active_dispute = True
    test_session.commit()

    service = IssuanceService(test_session, StubBlockchainGateway())
    with pytest.raises(EligibilityError) as exc:
        service.initiate_issuance(
            asset_id=asset.id,
            actor_id="ops-1",
            actor_role="operations",
            issuance_metadata={"batch_id": "B-101"},
        )

    assert "active_dispute" in exc.value.reasons


def test_blocked_issuance_due_to_freeze(test_session: Session) -> None:
    asset, _ = _create_verified_asset(test_session)
    asset.is_frozen = True
    test_session.commit()

    service = IssuanceService(test_session, StubBlockchainGateway())
    with pytest.raises(EligibilityError) as exc:
        service.initiate_issuance(
            asset_id=asset.id,
            actor_id="ops-1",
            actor_role="operations",
            issuance_metadata={"batch_id": "B-102"},
        )

    assert "asset_frozen" in exc.value.reasons


def test_eligibility_gate_failures(test_session: Session) -> None:
    asset, case = _create_verified_asset(test_session)
    asset.current_status = VerificationStatus.PENDING
    case.rules_snapshot = {
        "required_attestations": ["title_validation", "owner_identity", "tax_clearance"],
        "tokenization_policy": {"satisfied": False},
    }
    test_session.commit()

    test_session.refresh(case)
    gate = IssuanceEligibilityGate()
    decision = gate.evaluate(asset, case)

    assert decision.is_eligible is False
    assert "asset_not_verified" in decision.reasons
    assert "missing_attestation:tax_clearance" in decision.reasons
    assert "tokenization_policy_unsatisfied" in decision.reasons


def test_invalid_state_transition(test_session: Session) -> None:
    asset, _ = _create_verified_asset(test_session)
    issuance = TokenIssuance(asset_id=asset.id, stage=IssuanceStage.ELIGIBLE_FOR_TOKENIZATION)
    test_session.add(issuance)
    test_session.commit()

    service = IssuanceService(test_session, StubBlockchainGateway())
    with pytest.raises(InvalidIssuanceTransition):
        service._transition(issuance, IssuanceStage.TOKEN_MINTED)


def test_transfer_restriction_enforcement(test_session: Session) -> None:
    asset, _ = _create_verified_asset(test_session)
    service = IssuanceService(test_session, StubBlockchainGateway())

    assert service.validate_transfer(asset_id=asset.id).allowed is True

    asset.is_frozen = True
    test_session.commit()
    blocked = service.validate_transfer(asset_id=asset.id)
    assert blocked.allowed is False
    assert "asset_frozen" in blocked.reasons

    asset.is_frozen = False
    asset.has_active_dispute = True
    test_session.commit()
    blocked_by_dispute = service.validate_transfer(asset_id=asset.id, policy_rules={"transfers_allowed": True})
    assert blocked_by_dispute.allowed is False
    assert "active_dispute" in blocked_by_dispute.reasons

    asset.has_active_dispute = False
    test_session.commit()
    blocked_by_policy = service.validate_transfer(asset_id=asset.id, policy_rules={"transfers_allowed": False})
    assert blocked_by_policy.allowed is False
    assert "policy_blocked" in blocked_by_policy.reasons
