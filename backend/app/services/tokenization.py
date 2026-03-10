from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset
from app.models.audit import AuditEvent
from app.models.tokenization import (
    AssetComplianceBlock,
    ComplianceBlockStatus,
    IssuanceStatus,
    TokenizationIssuance,
    TokenizationModel,
    TokenizationPolicy,
)
from app.schemas.tokenization import TokenizationIssueRequest


class AssetNotFoundError(Exception):
    pass


class TokenizationEligibilityError(Exception):
    pass


@dataclass
class EligibilityResult:
    eligible: bool
    checks: dict


ARCHITECTURE_DECISION = {
    "alternatives": {
        "nft_only": {
            "pros": [
                "simple single-token representation",
                "easy uniqueness guarantees",
            ],
            "cons": [
                "weak support for compliant fractional ownership",
                "difficult liquidity partitioning without wrappers",
                "insufficient granularity for transfer controls by token class",
            ],
        },
        "dual_layer": {
            "pros": [
                "clean split between immutable identity NFT and fractional claim tokens",
                "supports partial liquidity while preserving singular legal identity",
                "enables policy-driven restrictions over fractional transfers",
            ],
            "cons": [
                "more operational complexity",
            ],
        },
    },
    "selected": "dual_layer",
    "rationale": "Dual-layer better matches RWA compliance, dispute handling, and partial ownership requirements.",
}


def evaluate_tokenization_eligibility(db: Session, asset: Asset, request: TokenizationIssueRequest) -> EligibilityResult:
    active_block = db.scalar(
        select(AssetComplianceBlock).where(
            AssetComplianceBlock.asset_id == asset.id,
            AssetComplianceBlock.status == ComplianceBlockStatus.ACTIVE,
        )
    )
    manual_ok = (not request.policy.requires_manual_approval) or request.manual_approved
    current_status_value = getattr(asset.current_status, "value", str(asset.current_status))
    verification_ok = current_status_value == request.policy.min_verification_status
    has_no_active_blocks = active_block is None
    fractional_ok = True
    if request.policy.tokenization_model == TokenizationModel.DUAL_LAYER and request.policy.allows_fractionalization:
        fractional_ok = all(
            [
                request.fractional_contract,
                request.fractional_token_class,
                request.fractional_total_supply,
            ]
        )

    checks = {
        "asset_status": current_status_value,
        "required_status": request.policy.min_verification_status,
        "verification_status_ok": verification_ok,
        "requires_manual_approval": request.policy.requires_manual_approval,
        "manual_approval_ok": manual_ok,
        "has_no_active_blocks": has_no_active_blocks,
        "active_block_type": active_block.block_type if active_block else None,
        "tokenization_model": request.policy.tokenization_model,
        "fractional_config_ok": bool(fractional_ok),
        "decision_basis": ARCHITECTURE_DECISION,
    }
    return EligibilityResult(
        eligible=verification_ok and manual_ok and has_no_active_blocks and bool(fractional_ok), checks=checks
    )


def issue_asset_tokens(db: Session, asset_id, request: TokenizationIssueRequest) -> TokenizationIssuance:
    asset = db.get(Asset, asset_id)
    if not asset:
        raise AssetNotFoundError("Asset not found")

    policy = db.scalar(select(TokenizationPolicy).where(TokenizationPolicy.asset_id == asset.id))
    if not policy:
        policy = TokenizationPolicy(asset_id=asset.id)
        db.add(policy)

    policy.tokenization_model = request.policy.tokenization_model
    policy.allows_fractionalization = request.policy.allows_fractionalization
    policy.min_verification_status = request.policy.min_verification_status
    policy.requires_manual_approval = request.policy.requires_manual_approval
    policy.transfer_restriction_mode = request.policy.transfer_restriction_mode
    policy.allowed_jurisdictions = request.policy.allowed_jurisdictions
    policy.whitelisted_wallets = request.policy.whitelisted_wallets
    policy.metadata_json = request.policy.metadata

    eligibility = evaluate_tokenization_eligibility(db, asset, request)

    issuance = db.scalar(select(TokenizationIssuance).where(TokenizationIssuance.asset_id == asset.id))
    if not issuance:
        issuance = TokenizationIssuance(asset_id=asset.id, policy=policy)
        db.add(issuance)

    if not eligibility.eligible:
        issuance.status = IssuanceStatus.BLOCKED
        issuance.eligibility_snapshot = eligibility.checks
        db.add(
            AuditEvent(
                asset_id=asset.id,
                actor_role="system",
                actor_id=request.requested_by,
                event_type="tokenization.issuance_blocked",
                event_payload=eligibility.checks,
            )
        )
        db.commit()
        raise TokenizationEligibilityError("Asset is not eligible for token issuance")

    issuance.status = IssuanceStatus.ISSUED
    issuance.identity_contract = request.identity_contract
    issuance.identity_token_id = request.identity_token_id
    issuance.fractional_contract = request.fractional_contract
    issuance.fractional_token_class = request.fractional_token_class
    issuance.fractional_total_supply = request.fractional_total_supply
    issuance.issuance_reference = request.issuance_reference
    issuance.eligibility_snapshot = eligibility.checks
    issuance.issued_at = datetime.now(timezone.utc)

    db.add(
        AuditEvent(
            asset_id=asset.id,
            actor_role="system",
            actor_id=request.requested_by,
            event_type="tokenization.issued",
            event_payload={
                "tokenization_model": request.policy.tokenization_model,
                "identity_contract": request.identity_contract,
                "identity_token_id": request.identity_token_id,
            },
        )
    )
    db.commit()
    db.refresh(issuance)
    db.refresh(policy)

    return issuance


def create_compliance_block(db: Session, asset_id, *, block_type, reason: str, created_by: str, metadata: dict):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise AssetNotFoundError("Asset not found")

    block = AssetComplianceBlock(
        asset_id=asset.id,
        block_type=block_type,
        reason=reason,
        created_by=created_by,
        metadata_json=metadata,
    )
    db.add(block)
    db.add(
        AuditEvent(
            asset_id=asset.id,
            actor_role="compliance",
            actor_id=created_by,
            event_type="asset.compliance_block_created",
            event_payload={"block_type": block_type, "reason": reason},
        )
    )
    db.commit()
    db.refresh(block)
    return block
