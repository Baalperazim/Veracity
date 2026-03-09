from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any
from verification_engine.asset_validator import AssetValidator
from verification_engine.registry import AssetRegistry

app = FastAPI(
    title="Veracity API",
    description="API for verifying and registering real-world assets in Nigeria.",
    version="0.1.0"
)

registry = AssetRegistry()


class AssetPayload(BaseModel):
    owner: str = Field(..., example="Adejoh Caleb")
    asset_type: str = Field(..., example="land")
    location: str = Field(..., example="Ibadan, Oyo State")
    size: str = Field(..., example="500sqm")
    metadata: Dict[str, Any] = Field(default_factory=dict)


@app.get("/")
def root():
    return {
        "product": "Veracity",
        "status": "running",
        "message": "Veracity asset verification API is live."
    }


@app.post("/assets/register")
def register_asset(payload: AssetPayload):
    asset_data = payload.model_dump()

    validator = AssetValidator(asset_data)
    record = validator.create_verification_record()

    registry.save_record(record)

    return {
        "message": "Asset registered successfully",
        "record": record
    }


@app.get("/assets/{asset_id}")
def get_asset(asset_id: str):
    record = registry.get_record(asset_id)

    if not record:
        raise HTTPException(status_code=404, detail="Asset not found")

    return record


@app.get("/assets/verify/{asset_id}")
def verify_asset(asset_id: str):
    exists = registry.asset_exists(asset_id)

    return {
        "asset_id": asset_id,
        "verified": exists
    }