import pytest

from app.models.asset import Asset, AssetType, VerificationStatus
from app.models.audit import AuditEvent
from app.models.verification import Attestation, VerificationCaseStatus, VerifierRole
from app.services.verification_workflow import (
    ActorContext,
    InvalidVerificationTransitionError,
    UnauthorizedVerificationActionError,
    approve_verification,
    claim_case,
    create_verification_case,
    detect_attestation_conflicts,
    escalate_to_dispute,
    evaluate_issuance_readiness,
    flag_conflict,
    list_cases_by_status,
    list_pending_cases,
    reject_verification,
    request_more_information,
    submit_document_metadata,
    transition_verification_status,
)


def _make_asset(test_session) -> Asset:
    asset = Asset(
        asset_type=AssetType.LAND,
        country_code="NG",
        state="Lagos",
        lga="Ikeja",
        locality="Allen",
        parcel_reference="PCL-001",
        area_sqm="500",
        owner_full_name="Ada Lovelace",
        owner_reference="OWNER-1",
        fingerprint="fp-001",
        canonical_payload={"parcel_reference": "PCL-001"},
        asset_metadata={"title": "Lagos parcel"},
    )
    test_session.add(asset)
    test_session.flush()
    return asset


def test_transition_verification_status_allows_valid_path() -> None:
    from app.models.verification import VerificationCase

    verification_case = VerificationCase(status=VerificationCaseStatus.OPEN)

    transition_verification_status(verification_case, to_status=VerificationCaseStatus.UNDER_REVIEW)
    assert verification_case.status == VerificationCaseStatus.UNDER_REVIEW

    transition_verification_status(verification_case, to_status=VerificationCaseStatus.APPROVED)
    assert verification_case.status == VerificationCaseStatus.APPROVED

    transition_verification_status(verification_case, to_status=VerificationCaseStatus.ISSUANCE_READY)
    assert verification_case.status == VerificationCaseStatus.ISSUANCE_READY


def test_transition_verification_status_rejects_invalid_path() -> None:
    from app.models.verification import VerificationCase

    verification_case = VerificationCase(status=VerificationCaseStatus.OPEN)

    with pytest.raises(InvalidVerificationTransitionError):
        transition_verification_status(verification_case, to_status=VerificationCaseStatus.ISSUED)


def test_list_pending_and_by_status(test_session) -> None:
    asset = _make_asset(test_session)
    case_a = create_verification_case(test_session, asset_id=asset.id)
    case_b = create_verification_case(test_session, asset_id=asset.id)
    transition_verification_status(case_b, to_status=VerificationCaseStatus.UNDER_REVIEW)
    case_c = create_verification_case(test_session, asset_id=asset.id)
    transition_verification_status(case_c, to_status=VerificationCaseStatus.UNDER_REVIEW)
    transition_verification_status(case_c, to_status=VerificationCaseStatus.REJECTED)
    test_session.commit()

    pending = list_pending_cases(test_session)
    under_review = list_cases_by_status(test_session, VerificationCaseStatus.UNDER_REVIEW)

    pending_ids = {case.id for case in pending}
    assert case_a.id in pending_ids
    assert case_b.id in pending_ids
    assert case_c.id not in pending_ids
    assert [case.id for case in under_review] == [case_b.id]


def test_claim_case_enforces_permissions(test_session) -> None:
    asset = _make_asset(test_session)
    verification_case = create_verification_case(test_session, asset_id=asset.id)
    test_session.commit()

    with pytest.raises(UnauthorizedVerificationActionError):
        claim_case(
            test_session,
            verification_case=verification_case,
            actor=ActorContext(actor_id="owner-1", role="owner"),
        )


def test_approval_flow_sets_verified_state_and_audit(test_session) -> None:
    asset = _make_asset(test_session)
    verification_case = create_verification_case(test_session, asset_id=asset.id)
    verifier = ActorContext(actor_id="verifier-1", role="verifier")

    claim_case(test_session, verification_case=verification_case, actor=verifier)
    approve_verification(test_session, verification_case=verification_case, actor=verifier, reason="all checks passed")

    test_session.refresh(asset)
    audit_events = test_session.query(AuditEvent).all()
    event_types = [event.event_type for event in audit_events]

    assert verification_case.status == VerificationCaseStatus.APPROVED
    assert asset.current_status == VerificationStatus.VERIFIED
    assert "verification.case_claimed" in event_types
    assert "verification.approved" in event_types


def test_rejection_flow_sets_rejected_state_and_blocks_eligibility(test_session) -> None:
    asset = _make_asset(test_session)
    verification_case = create_verification_case(test_session, asset_id=asset.id)
    verifier = ActorContext(actor_id="verifier-1", role="verifier")

    claim_case(test_session, verification_case=verification_case, actor=verifier)
    reject_verification(test_session, verification_case=verification_case, actor=verifier, reason="invalid deed")

    test_session.refresh(asset)
    assert verification_case.status == VerificationCaseStatus.REJECTED
    assert asset.current_status == VerificationStatus.REJECTED


def test_request_more_information_flow_and_owner_response(test_session) -> None:
    asset = _make_asset(test_session)
    verification_case = create_verification_case(test_session, asset_id=asset.id)
    verifier = ActorContext(actor_id="verifier-2", role="verifier")

    claim_case(test_session, verification_case=verification_case, actor=verifier)
    request_more_information(
        test_session,
        verification_case=verification_case,
        actor=verifier,
        reason="Need clearer boundary survey",
    )

    owner = ActorContext(actor_id="owner-1", role="owner")
    submit_document_metadata(
        test_session,
        verification_case=verification_case,
        actor=owner,
        document_type="boundary_survey",
        storage_pointer="s3://placeholder/survey-1.pdf",
        metadata={"version": 2},
    )

    test_session.refresh(verification_case)
    assert verification_case.status == VerificationCaseStatus.UNDER_REVIEW
    assert verification_case.info_request_reason is None


def test_invalid_transition_request_information_from_open_case(test_session) -> None:
    asset = _make_asset(test_session)
    verification_case = create_verification_case(test_session, asset_id=asset.id)

    with pytest.raises(InvalidVerificationTransitionError):
        request_more_information(
            test_session,
            verification_case=verification_case,
            actor=ActorContext(actor_id="verifier-2", role="verifier"),
            reason="Need correction",
        )


def test_conflict_flagging_and_dispute_initiation(test_session) -> None:
    asset = _make_asset(test_session)
    verification_case = create_verification_case(test_session, asset_id=asset.id)
    verifier = ActorContext(actor_id="verifier-2", role="verifier")

    claim_case(test_session, verification_case=verification_case, actor=verifier)
    flag_conflict(
        test_session,
        verification_case=verification_case,
        actor=verifier,
        reason="Contradictory title records",
    )

    test_session.refresh(asset)
    assert verification_case.status == VerificationCaseStatus.CONFLICTED
    assert asset.is_frozen is True

    escalate_to_dispute(
        test_session,
        verification_case=verification_case,
        actor=verifier,
        reason="Escalated to adjudication board",
    )

    test_session.refresh(asset)
    assert verification_case.status == VerificationCaseStatus.DISPUTED
    assert asset.has_active_dispute is True


def test_unauthorized_actions_are_rejected(test_session) -> None:
    asset = _make_asset(test_session)
    verification_case = create_verification_case(test_session, asset_id=asset.id)

    with pytest.raises(UnauthorizedVerificationActionError):
        approve_verification(
            test_session,
            verification_case=verification_case,
            actor=ActorContext(actor_id="auditor-1", role="auditor"),
            reason="should not pass",
        )


def test_detect_attestation_conflicts_flags_duplicates_and_conflicts() -> None:
    attestation_a1 = Attestation(
        verifier_role=VerifierRole.LAND_REGISTRY_OFFICER,
        verifier_id="verifier_1",
        provider="registry",
        attestation_type="title_validation",
        payload_hash="hash-1",
        payload={"status": "ok"},
    )
    attestation_a2 = Attestation(
        verifier_role=VerifierRole.LAND_REGISTRY_OFFICER,
        verifier_id="verifier_2",
        provider="registry",
        attestation_type="title_validation",
        payload_hash="hash-1",
        payload={"status": "ok"},
    )
    attestation_b = Attestation(
        verifier_role=VerifierRole.LAND_REGISTRY_OFFICER,
        verifier_id="verifier_3",
        provider="registry",
        attestation_type="title_validation",
        payload_hash="hash-2",
        payload={"status": "hold"},
    )

    report = detect_attestation_conflicts([attestation_a1, attestation_a2, attestation_b])

    assert len(report.duplicate_attestation_ids) == 2
    assert len(report.conflicting_attestation_ids) == 3
    assert report.has_conflicts is True


def test_evaluate_issuance_readiness_stub_reports_missing_requirements() -> None:
    from app.models.verification import VerificationCase

    verification_case = VerificationCase(status=VerificationCaseStatus.APPROVED)
    verification_case.attestations = [
        Attestation(
            verifier_role=VerifierRole.LAND_REGISTRY_OFFICER,
            verifier_id="registry_1",
            provider="registry",
            attestation_type="title_validation",
            payload_hash="hash-1",
            payload={"status": "ok"},
        )
    ]

    readiness = evaluate_issuance_readiness(verification_case)

    assert readiness.is_ready is False
    assert "missing_required_attesters:licensed_surveyor" in readiness.reasons


def test_evaluate_issuance_readiness_stub_ready_when_minimum_inputs_present() -> None:
    from app.models.verification import VerificationCase

    verification_case = VerificationCase(status=VerificationCaseStatus.APPROVED)
    verification_case.attestations = [
        Attestation(
            verifier_role=VerifierRole.LAND_REGISTRY_OFFICER,
            verifier_id="registry_1",
            provider="registry",
            attestation_type="title_validation",
            payload_hash="hash-1",
            payload={"status": "ok"},
        ),
        Attestation(
            verifier_role=VerifierRole.LICENSED_SURVEYOR,
            verifier_id="surveyor_1",
            provider="survey_authority",
            attestation_type="survey_validation",
            payload_hash="hash-2",
            payload={"status": "ok"},
        ),
    ]

    readiness = evaluate_issuance_readiness(verification_case)

    assert readiness.is_ready is True
    assert readiness.reasons == []
