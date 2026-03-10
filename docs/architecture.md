# Veracity Architecture (Phase 1)

## Scope
Phase 1 delivers a verification-first backend foundation for Nigerian land/property onboarding.

## Implemented modules

### 1) API Layer (FastAPI)
- `POST /api/v1/assets` for initial asset registration
- `GET /health` service probe

### 2) Verification Core
- canonical asset payload construction
- deterministic SHA-256 fingerprinting
- duplicate prevention using canonical fingerprint uniqueness

### 3) Persistence Layer
- PostgreSQL via SQLAlchemy ORM
- Alembic-managed schema
- core entities:
  - `assets`
  - `verification_cases`
  - `attestations`
  - `document_records`
  - `audit_events`

### 4) Auditability
- every registration writes an `asset.registration_submitted` audit event

## Deliberately deferred
- identity provider integrations (e.g., NIN adapters)
- document OCR/forensics
- onchain registry contracts
- transfer/dispute workflows
- frontend dashboard
