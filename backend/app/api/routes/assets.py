from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.asset import (
    AnchorPreparationRequest,
    AnchorPreparationResponse,
    AnchorRecordRequest,
    AnchorRecordResponse,
    AssetRegistrationRequest,
    AssetRegistrationResponse,
)
from app.services.anchoring import (
    AnchorAlreadyExistsError,
    AnchorNotFoundError,
    AnchorStateError,
    AssetNotFoundError,
    prepare_anchor,
    record_submitted_anchor,
)
from app.services.asset_registration import DuplicateAssetError, register_asset

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.post("", response_model=AssetRegistrationResponse, status_code=status.HTTP_201_CREATED)
def register_asset_endpoint(
    payload: AssetRegistrationRequest,
    db: Session = Depends(get_db_session),
) -> AssetRegistrationResponse:
    try:
        asset, verification_case = register_asset(db=db, payload=payload)
    except DuplicateAssetError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AssetRegistrationResponse(
        id=asset.id,
        fingerprint=asset.fingerprint,
        current_status=asset.current_status,
        verification_case_id=verification_case.id,
        created_at=asset.created_at,
    )


@router.post("/{asset_id}/anchors/prepare", response_model=AnchorPreparationResponse, status_code=status.HTTP_201_CREATED)
def prepare_asset_anchor_endpoint(
    asset_id: UUID,
    payload: AnchorPreparationRequest,
    db: Session = Depends(get_db_session),
) -> AnchorPreparationResponse:
    try:
        anchor = prepare_anchor(db=db, asset_id=asset_id, payload=payload)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AnchorAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return AnchorPreparationResponse(
        anchor_id=anchor.id,
        asset_id=anchor.asset_id,
        chain_id=anchor.chain_id,
        registry_address=anchor.registry_address,
        anchor_hash=anchor.anchor_hash,
        anchor_schema=anchor.anchor_schema,
        status=anchor.status,
        created_at=anchor.created_at,
    )


@router.post("/{asset_id}/anchors/{anchor_id}/record", response_model=AnchorRecordResponse)
def record_onchain_anchor_endpoint(
    asset_id: UUID,
    anchor_id: UUID,
    payload: AnchorRecordRequest,
    db: Session = Depends(get_db_session),
) -> AnchorRecordResponse:
    try:
        anchor = record_submitted_anchor(db=db, asset_id=asset_id, anchor_id=anchor_id, payload=payload)
    except AnchorNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AnchorStateError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return AnchorRecordResponse(
        anchor_id=anchor.id,
        asset_id=anchor.asset_id,
        status=anchor.status,
        tx_hash=anchor.tx_hash,
        block_number=anchor.block_number,
        updated_at=anchor.updated_at,
    )
