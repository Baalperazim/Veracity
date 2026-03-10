from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.verification import Attestation, VerificationCase, VerificationCaseStatus, VerifierRole


class InvalidVerificationTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class ConflictReport:
    duplicate_attestation_ids: list[UUID]
    conflicting_attestation_ids: list[UUID]

    @property
    def has_conflicts(self) -> bool:
        return bool(self.conflicting_attestation_ids)


@dataclass(frozen=True)
class IssuanceReadiness:
    is_ready: bool
    reasons: list[str]


ALLOWED_TRANSITIONS: dict[VerificationCaseStatus, set[VerificationCaseStatus]] = {
    VerificationCaseStatus.OPEN: {VerificationCaseStatus.UNDER_REVIEW, VerificationCaseStatus.REJECTED},
    VerificationCaseStatus.UNDER_REVIEW: {
        VerificationCaseStatus.CONFLICTED,
        VerificationCaseStatus.APPROVED,
        VerificationCaseStatus.REJECTED,
    },
    VerificationCaseStatus.CONFLICTED: {VerificationCaseStatus.UNDER_REVIEW, VerificationCaseStatus.REJECTED},
    VerificationCaseStatus.APPROVED: {VerificationCaseStatus.ISSUANCE_READY, VerificationCaseStatus.REJECTED},
    VerificationCaseStatus.ISSUANCE_READY: {VerificationCaseStatus.ISSUED},
    VerificationCaseStatus.REJECTED: set(),
    VerificationCaseStatus.ISSUED: set(),
}


REQUIRED_ISSUANCE_ROLES = {
    VerifierRole.LAND_REGISTRY_OFFICER,
    VerifierRole.LICENSED_SURVEYOR,
}


def create_verification_case(
    db: Session,
    *,
    asset_id: UUID,
    rules_snapshot: dict | None = None,
) -> VerificationCase:
    verification_case = VerificationCase(
        asset_id=asset_id,
        status=VerificationCaseStatus.OPEN,
        rules_snapshot=rules_snapshot or {"version": "v1", "name": "base_registration"},
    )
    db.add(verification_case)
    db.flush()
    return verification_case


def transition_verification_status(
    verification_case: VerificationCase,
    *,
    to_status: VerificationCaseStatus,
    decision_reason: str | None = None,
) -> VerificationCase:
    current_status = verification_case.status
    if to_status == current_status:
        return verification_case

    if to_status not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidVerificationTransitionError(
            f"Transition from {current_status.value} to {to_status.value} is not permitted"
        )

    verification_case.status = to_status
    verification_case.decision_reason = decision_reason
    return verification_case


def detect_attestation_conflicts(attestations: list[Attestation]) -> ConflictReport:
    by_type_and_hash: dict[tuple[str, str], list[Attestation]] = defaultdict(list)
    by_type: dict[str, set[str]] = defaultdict(set)

    for attestation in attestations:
        if attestation.is_revoked:
            continue
        by_type_and_hash[(attestation.attestation_type, attestation.payload_hash)].append(attestation)
        by_type[attestation.attestation_type].add(attestation.payload_hash)

    duplicates: list[UUID] = []
    for entries in by_type_and_hash.values():
        if len(entries) > 1:
            duplicates.extend([attestation.id for attestation in entries])

    conflicts: list[UUID] = []
    for attestation_type, payload_hashes in by_type.items():
        if len(payload_hashes) <= 1:
            continue

        for attestation in attestations:
            if attestation.is_revoked:
                continue
            if attestation.attestation_type == attestation_type:
                conflicts.append(attestation.id)

    return ConflictReport(
        duplicate_attestation_ids=sorted(set(duplicates)),
        conflicting_attestation_ids=sorted(set(conflicts)),
    )


def evaluate_issuance_readiness(verification_case: VerificationCase) -> IssuanceReadiness:
    """Readiness foundation stub. Keeps decision local until integrations are added."""

    reasons: list[str] = []
    if verification_case.status != VerificationCaseStatus.APPROVED:
        reasons.append("verification_case_not_approved")

    active_attestations = [attestation for attestation in verification_case.attestations if not attestation.is_revoked]
    conflict_report = detect_attestation_conflicts(active_attestations)
    if conflict_report.has_conflicts:
        reasons.append("attestation_conflicts_detected")

    attester_roles = {attestation.verifier_role for attestation in active_attestations}
    missing_roles = sorted(role.value for role in REQUIRED_ISSUANCE_ROLES - attester_roles)
    if missing_roles:
        reasons.append(f"missing_required_attesters:{','.join(missing_roles)}")

    return IssuanceReadiness(is_ready=not reasons, reasons=reasons)
