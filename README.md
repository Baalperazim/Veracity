# Veracity

Veracity is a verification-first real-world asset (RWA) infrastructure platform, starting with land/property assets in Nigeria.

This repository currently contains **Phase 1 foundation + Phase 3 anchoring baseline**:
- FastAPI backend service
- PostgreSQL persistence with SQLAlchemy 2.x
- Alembic migrations
- Deterministic asset fingerprinting from canonicalized asset data
- Asset registration endpoint that automatically opens a verification case and writes an audit event
- Pytest coverage for fingerprinting and registration flow
- Minimal blockchain anchor workflow (contract + backend preparation/recording APIs)

## Monorepo structure (Phase 1)

```text
.
├── backend/
│   ├── app/
│   │   ├── api/routes/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── alembic/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
└── docker-compose.yml
```

## Local development

### 1) Start database + API

```bash
docker compose up --build
```

API base URL: `http://localhost:8000`

### 2) Run migrations manually (optional)

```bash
cd backend
alembic upgrade head
```

### 3) Run tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

## API (Phase 1)

### `GET /health`
Basic service liveness probe.

### `POST /api/v1/assets`
Registers a candidate asset for verification.

Behavior:
- canonicalizes key asset fields
- computes deterministic SHA-256 fingerprint
- rejects duplicates by canonical fingerprint
- writes asset row + verification case + audit event

Example request:

```json
{
  "asset_type": "land",
  "country_code": "NG",
  "state": "Lagos",
  "lga": "Ikeja",
  "locality": "Alausa",
  "parcel_reference": "IKJ-PLT-8",
  "area_sqm": "450",
  "owner_full_name": "Amina Yusuf",
  "owner_reference": "NIN-0099",
  "metadata": {
    "title_number": "LND-23"
  },
  "submitted_by": "owner_amina"
}
```

## Notes on scope

Current scope still intentionally excludes frontend UX, full transfer flows, and fractionalization. Phase 3 adds only minimal immutable anchoring.
