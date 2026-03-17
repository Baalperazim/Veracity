from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, VerificationStatus
from app.models.audit import AuditEvent
from app.models.verification import (
    Attestation,
    VerificationCase,
    VerificationCaseStatus,
    VerificationDocument,
    VerifierRole,
)


class InvalidVerificationTransitionError(ValueError):
    pass


class UnauthorizedVerificationActionError(PermissionError):
    pass


@dataclass(frozen=True)
class ActorContext:
    actor_id: str
    role: str


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
    VerificationCaseStatus.OPEN: {
        VerificationCaseStatus.UNDER_REVIEW,
        VerificationCaseStatus.REJECTED,
    },
    VerificationCaseStatus.UNDER_REVIEW: {
        VerificationCaseStatus.NEEDS_INFORMATION,
        VerificationCaseStatus.CONFLICTED,
        VerificationCaseStatus.DISPUTED,
        VerificationCaseStatus.APPROVED,
        VerificationCaseStatus.REJECTED,
    },
    VerificationCaseStatus.NEEDS_INFORMATION: {
        VerificationCaseStatus.UNDER_REVIEW,
        VerificationCaseStatus.REJECTED,
    },
    VerificationCaseStatus.CONFLICTED: {
        VerificationCaseStatus.UNDER_REVIEW,
        VerificationCaseStatus.DISPUTED,
        VerificationCaseStatus.REJECTED,
    },
    VerificationCaseStatus.DISPUTED: set(),
    VerificationCaseStatus.APPROVED: {
        VerificationCaseStatus.ISSUANCE_READY,
        VerificationCaseStatus.CONFLICTED,
        VerificationCaseStatus.DISPUTED,
    },
    VerificationCaseStatus.ISSUANCE_READY: {VerificationCaseStatus.ISSUED},
    VerificationCaseStatus.REJECTED: set(),
    VerificationCaseStatus.ISSUED: set(),
}


ROLE_PERMISSIONS: dict[str, set[str]] = {
    "owner": {
        "submit_document_metadata",
        "respond_to_information_request",
    },
    "verifier": {
        "claim_case",
        "review_case",
        "request_more_information",
        "approve_verification",
        "reject_verification",
        "flag_conflict",
        "initiate_dispute",
    },
    "registrar": {
        "claim_case",
        "review_case",
        "request_more_information",
        "approve_verification",
        "reject_verification",
        "flag_conflict",
        "initiate_dispute",
    },
    "admin": {
        "claim_case",
        "review_case",
        "request_more_information",
        "approve_verification",
        "reject_verification",
        "flag_conflict",
        "initiate_dispute",
    },
    "auditor": {
        "review_case",
    },
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


def list_pending_cases(db: Session) -> list[VerificationCase]:
    pending_statuses = [
        VerificationCaseStatus.OPEN,
        VerificationCaseStatus.UNDER_REVIEW,
        VerificationCaseStatus.NEEDS_INFORMATION,
        VerificationCaseStatus.CONFLICTED,
    ]
    return list(
        db.scalars(
            select(VerificationCase)
            .where(VerificationCase.status.in_(pending_statuses))
            .order_by(VerificationCase.created_at.asc())
        )
    )


def list_cases_by_status(db: Session, status: VerificationCaseStatus) -> list[VerificationCase]:
    return list(
        db.scalars(
            select(VerificationCase)
            .where(VerificationCase.status == status)
            .order_by(VerificationCase.created_at.asc())
        )
    )


def claim_case(db: Session, *, verification_case: VerificationCase, actor: ActorContext) -> VerificationCase:
    _require_permission(actor, "claim_case")
    if verification_case.assigned_reviewer_id and verification_case.assigned_reviewer_id != actor.actor_id:
        raise UnauthorizedVerificationActionError("Verification case is already assigned to another reviewer")

    verification_case.assigned_reviewer_id = actor.actor_id
    verification_case.assigned_reviewer_role = actor.role
    verification_case.claimed_at = datetime.now(timezone.utc)
    if verification_case.status == VerificationCaseStatus.OPEN:
        transition_verification_status(verification_case, to_status=VerificationCaseStatus.UNDER_REVIEW)

    _record_audit(
        db,
        verification_case=verification_case,
        actor=actor,
        event_type="verification.case_claimed",
        event_payload={"status": verification_case.status.value},
    )
    db.commit()
    db.refresh(verification_case)
    return verification_case


def get_case_review_packet(db: Session, *, verification_case_id: UUID, actor: ActorContext) -> dict:
    _require_permission(actor, "review_case")
    verification_case = db.get(VerificationCase, verification_case_id)
    if not verification_case:
        raise ValueError("Verification case not found")

    asset = db.get(Asset, verification_case.asset_id)
    documents = list(
        db.scalars(
            select(VerificationDocument).where(VerificationDocument.verification_case_id == verification_case.id)
        )
    )

    return {
        "case_id": str(verification_case.id),
        "status": verification_case.status.value,
        "asset_metadata": asset.asset_metadata if asset else {},
        "documents": [
            {
                "id": str(document.id),
                "document_type": document.document_type,
                "storage_pointer": document.storage_pointer,
                "submitter_id": document.submitter_id,
                "submitter_role": document.submitter_role,
                "submitted_at": document.submitted_at.isoformat() if document.submitted_at else None,
                "reviewer_notes": document.reviewer_notes,
                "metadata": document.metadata_json,
            }
            for document in documents
        ],
    }


def submit_document_metadata(
    db: Session,
    *,
    verification_case: VerificationCase,
    actor: ActorContext,
    document_type: str,
    storage_pointer: str,
    metadata: dict | None = None,
    reviewer_notes: str | None = None,
) -> VerificationDocument:
    _require_permission(actor, "submit_document_metadata")
    document = VerificationDocument(
        asset_id=verification_case.asset_id,
        verification_case_id=verification_case.id,
        document_type=document_type,
        storage_pointer=storage_pointer,
        submitter_id=actor.actor_id,
        submitter_role=actor.role,
        reviewer_notes=reviewer_notes,
        metadata_json=metadata or {},
    )
    db.add(document)

    if verification_case.status == VerificationCaseStatus.NEEDS_INFORMATION:
        transition_verification_status(verification_case, to_status=VerificationCaseStatus.UNDER_REVIEW)
        verification_case.info_request_reason = None

    _record_audit(
        db,
        verification_case=verification_case,
        actor=actor,
        event_type="verification.document_metadata_submitted",
        event_payload={
            "document_type": document_type,
            "storage_pointer": storage_pointer,
        },
    )
    db.commit()
    db.refresh(document)
    return document


def request_more_information(
    db: Session,
    *,
    verification_case: VerificationCase,
    actor: ActorContext,
    reason: str,
) -> VerificationCase:
    _require_permission(actor, "request_more_information")
    transition_verification_status(verification_case, to_status=VerificationCaseStatus.NEEDS_INFORMATION)
    verification_case.info_request_reason = reason

    _set_asset_under_review(db, verification_case.asset_id)
    _record_audit(
        db,
        verification_case=verification_case,
        actor=actor,
        event_type="verification.information_requested",
        event_payload={"reason": reason},
    )
    db.commit()
    db.refresh(verification_case)
    return verification_case


def approve_verification(
    db: Session,
    *,
    verification_case: VerificationCase,
    actor: ActorContext,
    reason: str | None = None,
) -> VerificationCase:
    _require_permission(actor, "approve_verification")
    transition_verification_status(
        verification_case,
        to_status=VerificationCaseStatus.APPROVED,
        decision_reason=reason,
    )
    asset = db.get(Asset, verification_case.asset_id)
    if asset:
        asset.current_status = VerificationStatus.VERIFIED

    _record_audit(
        db,
        verification_case=verification_case,
        actor=actor,
        event_type="verification.approved",
        event_payload={"reason": reason},
    )
    db.commit()
    db.refresh(verification_case)
    return verification_case


def reject_verification(
    db: Session,
    *,
    verification_case: VerificationCase,
    actor: ActorContext,
    reason: str,
) -> VerificationCase:
    _require_permission(actor, "reject_verification")
    transition_verification_status(
        verification_case,
        to_status=VerificationCaseStatus.REJECTED,
        decision_reason=reason,
    )
    asset = db.get(Asset, verification_case.asset_id)
    if asset:
        asset.current_status = VerificationStatus.REJECTED

    _record_audit(
        db,
        verification_case=verification_case,
        actor=actor,
        event_type="verification.rejected",
        event_payload={"reason": reason},
    )
    db.commit()
    db.refresh(verification_case)
    return verification_case


def flag_conflict(
    db: Session,
    *,
    verification_case: VerificationCase,
    actor: ActorContext,
    reason: str,
) -> VerificationCase:
    _require_permission(actor, "flag_conflict")
    transition_verification_status(verification_case, to_status=VerificationCaseStatus.CONFLICTED)
    verification_case.conflict_reason = reason

    asset = db.get(Asset, verification_case.asset_id)
    if asset:
        asset.current_status = VerificationStatus.UNDER_REVIEW
        asset.is_frozen = True

    _record_audit(
        db,
        verification_case=verification_case,
        actor=actor,
        event_type="verification.conflict_flagged",
        event_payload={"reason": reason},
    )
    db.commit()
    db.refresh(verification_case)
    return verification_case


def escalate_to_dispute(
    db: Session,
    *,
    verification_case: VerificationCase,
    actor: ActorContext,
    reason: str,
) -> VerificationCase:
    _require_permission(actor, "initiate_dispute")
    transition_verification_status(verification_case, to_status=VerificationCaseStatus.DISPUTED)
    verification_case.dispute_reason = reason

    asset = db.get(Asset, verification_case.asset_id)
    if asset:
        asset.has_active_dispute = True
        asset.is_frozen = True
        asset.current_status = VerificationStatus.UNDER_REVIEW

    _record_audit(
        db,
        verification_case=verification_case,
        actor=actor,
        event_type="verification.dispute_initiated",
        event_payload={"reason": reason},
    )
    db.commit()
    db.refresh(verification_case)
    return verification_case


def detect_attestation_conflicts(attestations: list[Attestation]) -> ConflictReport:
    by_type_and_hash: dict[tuple[str, str], list[tuple[int, Attestation]]] = defaultdict(list)
    by_type: dict[str, set[str]] = defaultdict(set)

    for index, attestation in enumerate(attestations):
        if attestation.is_revoked:
            continue
        by_type_and_hash[(attestation.attestation_type, attestation.payload_hash)].append((index, attestation))
        by_type[attestation.attestation_type].add(attestation.payload_hash)

    duplicates: list[UUID] = []
    for entries in by_type_and_hash.values():
        if len(entries) > 1:
            for index, attestation in entries:
                duplicates.append(attestation.id or UUID(int=index + 1))

    conflicts: list[UUID] = []
    for attestation_type, payload_hashes in by_type.items():
        if len(payload_hashes) <= 1:
            continue

        for index, attestation in enumerate(attestations):
            if attestation.is_revoked:
                continue
            if attestation.attestation_type == attestation_type:
                conflicts.append(attestation.id or UUID(int=index + 1))

    return ConflictReport(
        duplicate_attestation_ids=duplicates,
        conflicting_attestation_ids=conflicts,
    )


def evaluate_issuance_readiness(verification_case: VerificationCase) -> IssuanceReadiness:
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


def _record_audit(
    db: Session,
    *,
    verification_case: VerificationCase,
    actor: ActorContext,
    event_type: str,
    event_payload: dict,
) -> None:
    db.add(
        AuditEvent(
            asset_id=verification_case.asset_id,
            actor_role=actor.role,
            actor_id=actor.actor_id,
            event_type=event_type,
            event_payload={
                "verification_case_id": str(verification_case.id),
                **event_payload,
            },
        )
    )


def _set_asset_under_review(db: Session, asset_id: UUID) -> None:
    asset = db.get(Asset, asset_id)
    if asset:
        asset.current_status = VerificationStatus.UNDER_REVIEW


def _require_permission(actor: ActorContext, action: str) -> None:
    allowed_actions = ROLE_PERMISSIONS.get(actor.role, set())
    if action not in allowed_actions:
        raise UnauthorizedVerificationActionError(
            f"Role '{actor.role}' cannot perform verification action '{action}'"
        )
