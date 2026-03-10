from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.tokenization import (
    ComplianceBlockCreateRequest,
    ComplianceBlockResponse,
    TokenizationIssueRequest,
    TokenizationIssueResponse,
)
from app.services.tokenization import (
    AssetNotFoundError,
    TokenizationEligibilityError,
    create_compliance_block,
    issue_asset_tokens,
)

router = APIRouter(prefix="/api/v1/assets", tags=["tokenization"])


@router.post("/{asset_id}/tokenization/issue", response_model=TokenizationIssueResponse)
def issue_asset_tokenization(
    asset_id: UUID,
    payload: TokenizationIssueRequest,
    db: Session = Depends(get_db_session),
) -> TokenizationIssueResponse:
    try:
        issuance = issue_asset_tokens(db=db, asset_id=asset_id, request=payload)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TokenizationEligibilityError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return TokenizationIssueResponse(
        asset_id=issuance.asset_id,
        issuance_id=issuance.id,
        status=issuance.status,
        tokenization_model=issuance.policy.tokenization_model,
        transfer_restriction_mode=issuance.policy.transfer_restriction_mode,
        eligibility_snapshot=issuance.eligibility_snapshot,
        issued_at=issuance.issued_at,
    )


@router.post("/{asset_id}/tokenization/blocks", response_model=ComplianceBlockResponse, status_code=status.HTTP_201_CREATED)
def create_asset_block(
    asset_id: UUID,
    payload: ComplianceBlockCreateRequest,
    db: Session = Depends(get_db_session),
) -> ComplianceBlockResponse:
    try:
        block = create_compliance_block(
            db=db,
            asset_id=asset_id,
            block_type=payload.block_type,
            reason=payload.reason,
            created_by=payload.created_by,
            metadata=payload.metadata,
        )
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return ComplianceBlockResponse(
        block_id=block.id,
        asset_id=block.asset_id,
        block_type=block.block_type,
        status=block.status,
        reason=block.reason,
    )
