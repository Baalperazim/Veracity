from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, VerificationStatus
from app.models.audit import AuditEvent
from app.models.issuance import IssuanceStage, TokenIssuance
from app.models.verification import VerificationCase


class EligibilityError(Exception):
    def __init__(self, reasons: list[str]):
        self.reasons = reasons
        super().__init__("Asset is not eligible for token issuance")


class InvalidIssuanceTransition(Exception):
    pass


@dataclass(frozen=True)
class EligibilityDecision:
    is_eligible: bool
    reasons: list[str]


@dataclass(frozen=True)
class TransferDecision:
    allowed: bool
    reasons: list[str]


@dataclass(frozen=True)
class OnchainAnchorRequest:
    asset_fingerprint: str
    registry_record_reference: str
    issuance_metadata: dict
    issuance_timestamp: str


@dataclass(frozen=True)
class BlockchainMintResult:
    token_id: str
    anchor_reference: str


class BlockchainGateway(Protocol):
    def mint_asset_token(self, request: OnchainAnchorRequest) -> BlockchainMintResult:
        """Mint a token and persist an immutable anchor to a chain-backed system."""


class IssuanceEligibilityGate:
    def evaluate(self, asset: Asset, verification_case: VerificationCase | None) -> EligibilityDecision:
        reasons: list[str] = []
        if asset.current_status != VerificationStatus.VERIFIED:
            reasons.append("asset_not_verified")
        if asset.has_active_dispute:
            reasons.append("active_dispute")
        if asset.is_frozen:
            reasons.append("asset_frozen")

        if verification_case is None:
            reasons.append("missing_verification_case")
        else:
            required = verification_case.rules_snapshot.get("required_attestations", [])
            attested = {attestation.attestation_type for attestation in verification_case.attestations}
            for required_attestation in required:
                if required_attestation not in attested:
                    reasons.append(f"missing_attestation:{required_attestation}")

            token_policy = verification_case.rules_snapshot.get("tokenization_policy", {})
            if not token_policy.get("satisfied", False):
                reasons.append("tokenization_policy_unsatisfied")

        return EligibilityDecision(is_eligible=len(reasons) == 0, reasons=reasons)


class TransferRestrictionPolicy:
    def evaluate(self, asset: Asset, policy_rules: dict | None = None) -> TransferDecision:
        reasons: list[str] = []
        if asset.is_frozen:
            reasons.append("asset_frozen")
        if asset.has_active_dispute:
            reasons.append("active_dispute")
        if asset.current_status != VerificationStatus.VERIFIED:
            reasons.append("verification_invalid")

        if policy_rules and policy_rules.get("transfers_allowed") is False:
            reasons.append("policy_blocked")

        return TransferDecision(allowed=len(reasons) == 0, reasons=reasons)


class OnchainAnchorFactory:
    @staticmethod
    def build(asset: Asset, issuance_metadata: dict, issuance_timestamp: datetime) -> OnchainAnchorRequest:
        return OnchainAnchorRequest(
            asset_fingerprint=asset.fingerprint,
            registry_record_reference=f"asset:{asset.id}",
            issuance_metadata=issuance_metadata,
            issuance_timestamp=issuance_timestamp.replace(tzinfo=timezone.utc).isoformat(),
        )


class IssuanceService:
    _valid_transitions: dict[IssuanceStage, set[IssuanceStage]] = {
        IssuanceStage.ELIGIBLE_FOR_TOKENIZATION: {IssuanceStage.ISSUANCE_PENDING},
        IssuanceStage.ISSUANCE_PENDING: {IssuanceStage.ISSUANCE_AUTHORIZED},
        IssuanceStage.ISSUANCE_AUTHORIZED: {IssuanceStage.TOKEN_MINTED},
        IssuanceStage.TOKEN_MINTED: {IssuanceStage.ISSUANCE_COMPLETED},
        IssuanceStage.ISSUANCE_COMPLETED: set(),
    }

    def __init__(
        self,
        db: Session,
        blockchain_gateway: BlockchainGateway,
        eligibility_gate: IssuanceEligibilityGate | None = None,
    ) -> None:
        self.db = db
        self.blockchain_gateway = blockchain_gateway
        self.eligibility_gate = eligibility_gate or IssuanceEligibilityGate()

    def initiate_issuance(
        self,
        *,
        asset_id: UUID,
        actor_id: str,
        actor_role: str,
        issuance_metadata: dict,
    ) -> TokenIssuance:
        asset = self.db.get(Asset, asset_id)
        if asset is None:
            raise ValueError("Asset not found")

        verification_case = self.db.scalar(
            select(VerificationCase).where(VerificationCase.asset_id == asset_id).order_by(VerificationCase.created_at.desc())
        )
        decision = self.eligibility_gate.evaluate(asset, verification_case)
        if not decision.is_eligible:
            self._add_audit(asset.id, actor_role, actor_id, "issuance.blocked", {"reasons": decision.reasons})
            self.db.commit()
            raise EligibilityError(decision.reasons)

        issuance = asset.issuance or TokenIssuance(
            asset_id=asset.id,
            issuance_metadata=issuance_metadata,
            stage=IssuanceStage.ELIGIBLE_FOR_TOKENIZATION,
        )
        if asset.issuance is None:
            self.db.add(issuance)

        self._add_audit(asset.id, actor_role, actor_id, "issuance.requested", {"metadata": issuance_metadata})

        self._transition(issuance, IssuanceStage.ISSUANCE_PENDING)
        self._transition(issuance, IssuanceStage.ISSUANCE_AUTHORIZED)

        now = datetime.now(timezone.utc)
        anchor_request = OnchainAnchorFactory.build(asset, issuance_metadata, now)
        mint_result = self.blockchain_gateway.mint_asset_token(anchor_request)

        issuance.onchain_anchor_payload = {
            "asset_fingerprint": anchor_request.asset_fingerprint,
            "registry_record_reference": anchor_request.registry_record_reference,
            "issuance_metadata": anchor_request.issuance_metadata,
            "issuance_timestamp": anchor_request.issuance_timestamp,
        }
        issuance.onchain_anchor_reference = mint_result.anchor_reference
        issuance.minted_token_id = mint_result.token_id

        self._transition(issuance, IssuanceStage.TOKEN_MINTED)
        self._transition(issuance, IssuanceStage.ISSUANCE_COMPLETED)
        issuance.completed_at = now

        self.db.commit()
        self.db.refresh(issuance)
        return issuance

    def validate_transfer(self, *, asset_id: UUID, policy_rules: dict | None = None) -> TransferDecision:
        asset = self.db.get(Asset, asset_id)
        if asset is None:
            raise ValueError("Asset not found")

        restriction = TransferRestrictionPolicy().evaluate(asset, policy_rules)
        if not restriction.allowed:
            self._add_audit(asset.id, "system", "transfer_policy", "transfer.blocked", {"reasons": restriction.reasons})
            self.db.commit()
        return restriction

    def _transition(self, issuance: TokenIssuance, to_stage: IssuanceStage) -> None:
        allowed = self._valid_transitions[issuance.stage]
        if to_stage not in allowed:
            raise InvalidIssuanceTransition(f"Invalid transition from {issuance.stage} to {to_stage}")

        issuance.stage = to_stage
        event_map = {
            IssuanceStage.ISSUANCE_PENDING: "issuance.pending",
            IssuanceStage.ISSUANCE_AUTHORIZED: "issuance.authorized",
            IssuanceStage.TOKEN_MINTED: "issuance.token_minted",
            IssuanceStage.ISSUANCE_COMPLETED: "issuance.completed",
        }
        event_type = event_map.get(to_stage)
        if event_type:
            self._add_audit(issuance.asset_id, "system", "issuance_engine", event_type, {"stage": to_stage.value})

    def _add_audit(self, asset_id: UUID, actor_role: str, actor_id: str, event_type: str, payload: dict) -> None:
        self.db.add(
            AuditEvent(
                asset_id=asset_id,
                actor_role=actor_role,
                actor_id=actor_id,
                event_type=event_type,
                event_payload=payload,
            )
        )
