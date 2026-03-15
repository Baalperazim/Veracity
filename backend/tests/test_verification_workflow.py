import pytest

from app.models.verification import Attestation, VerificationCase, VerificationCaseStatus, VerifierRole
from app.services.verification_workflow import (
    InvalidVerificationTransitionError,
    detect_attestation_conflicts,
    evaluate_issuance_readiness,
    transition_verification_status,
)


def test_transition_verification_status_allows_valid_path() -> None:
    verification_case = VerificationCase(status=VerificationCaseStatus.OPEN)

    transition_verification_status(verification_case, to_status=VerificationCaseStatus.UNDER_REVIEW)
    assert verification_case.status == VerificationCaseStatus.UNDER_REVIEW

    transition_verification_status(verification_case, to_status=VerificationCaseStatus.APPROVED)
    assert verification_case.status == VerificationCaseStatus.APPROVED

    transition_verification_status(verification_case, to_status=VerificationCaseStatus.ISSUANCE_READY)
    assert verification_case.status == VerificationCaseStatus.ISSUANCE_READY


def test_transition_verification_status_rejects_invalid_path() -> None:
    verification_case = VerificationCase(status=VerificationCaseStatus.OPEN)

    with pytest.raises(InvalidVerificationTransitionError):
        transition_verification_status(verification_case, to_status=VerificationCaseStatus.ISSUED)


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
