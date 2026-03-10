from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.schemas.asset import AssetRegistrationRequest, AssetRegistrationResponse
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
