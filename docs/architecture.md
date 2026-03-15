# Veracity Architecture (Phase 4)
# Veracity Architecture (Phase 1 + Phase 3 Anchoring Baseline)

## Scope
Phase 4 extends the verification-first backend with tokenization eligibility and issuance architecture for regulated RWA onboarding.

## Implemented modules

### 1) Tokenization policy model
- `tokenization_policies` binds one policy per asset.
- policy controls:
  - tokenization model (`nft_only` or `dual_layer`)
  - fractionalization flag
  - minimum verification status gate
  - manual approval gate
  - transfer restriction mode (`open`, `whitelist_only`, `jurisdiction_lock`)
  - jurisdiction and wallet allowlists

### 2) Eligibility checks
Eligibility is computed before issuance using deterministic checks:
- verification status must satisfy policy threshold
- manual approval must be supplied where required
- no active compliance block (freeze/dispute/regulatory hold)
- when dual-layer + fractionalization is enabled, fractional token parameters must be complete

A structured eligibility snapshot is persisted to support audit replay.

### 3) Issuance workflow design
`POST /api/v1/assets/{asset_id}/tokenization/issue`
1. Load or create policy for the asset
2. Evaluate eligibility checks
3. If ineligible, mark issuance as `blocked` and write audit event
4. If eligible, create/update issuance as `issued`, store identity/fractional token references, write audit event

### 4) Freeze/dispute blocks
`POST /api/v1/assets/{asset_id}/tokenization/blocks`
- creates active compliance blocks (`freeze`, `dispute`, `regulatory_hold`)
- active blocks halt issuance eligibility
- block creation is auditable through `asset.compliance_block_created`

### 5) Transfer restriction model
Policy-level transfer control primitives are now modeled and persisted:
- `open`: no transfer gate
- `whitelist_only`: transfer constrained to approved wallets
- `jurisdiction_lock`: transfer constrained by allowed jurisdictions

Execution enforcement is deferred to onchain adapter/runtime phases, but policy contract is implemented.

### 6) NFT-only vs dual-layer comparison and decision
Two architectures were evaluated:

#### NFT-only
Pros:
- simple unique identity representation
- easier baseline issuance

Cons:
- weak native fractional ownership support
- requires wrappers or synthetic mechanisms for liquidity partitioning
- coarse transfer/compliance granularity

#### Dual-layer (chosen)
Pros:
- preserves singular asset identity NFT
- supports compliant fractional claims via dedicated token class/supply
- cleaner compliance controls for partial ownership lifecycle

Cons:
- greater operational complexity

**Decision:** Dual-layer is the stronger architecture for regulated property RWA use-cases and is now the default policy foundation.

### 5) Blockchain Anchoring (Phase 3 baseline)
- minimal `AssetRegistry` smart contract for immutable asset anchors
- deterministic backend anchor payload + hash preparation
- anchor lifecycle persistence (`prepared` -> `submitted` -> `confirmed`)
- API support to prepare anchor records and attach tx metadata

## Deliberately deferred
- onchain deployment and settlement adapters
- transfer execution engine and smart-contract hooks
- block release workflows and case-management UI
- jurisdiction oracle/provider integrations
- identity provider integrations (e.g., NIN adapters)
- document OCR/forensics
- transfer/dispute workflows
- fractionalization/token economics
- frontend dashboard
