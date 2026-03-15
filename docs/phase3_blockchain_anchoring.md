# Phase 3: Blockchain Anchoring Design

## 1) Smart contract architecture decision

**Decision:** deploy a single-purpose `AssetRegistry` contract that only stores immutable anchor commitments keyed by offchain `asset_id`.

Why this shape in Phase 3:
- minimizes attack surface before transfer/fractionalization logic is introduced
- keeps gas and storage predictable (single write per asset)
- gives a canonical onchain event (`AssetAnchored`) that external verifiers can index

Deferred to later phases:
- ownership transfer logic
- tokenization/fractionalization
- complex role delegation and upgradeability patterns

## 2) Minimal asset registry contract

Contract location: `contracts/src/AssetRegistry.sol`.

Interface contract assumptions:
- `anchorAsset(bytes32 assetId, bytes32 anchorHash, string anchorURI)`
- `getAnchor(bytes32 assetId)`
- `AssetAnchored(bytes32 indexed assetId, bytes32 indexed anchorHash, string anchorURI, address indexed recorder)`

The contract enforces one anchor per `assetId` and only allows the configured owner to write.

## 3) Onchain anchor recording design

Offchain backend computes an anchor payload:
- `schema`
- `asset_id`
- `fingerprint`
- `canonical_payload`

The payload is deterministically serialized (sorted JSON, compact separators) and hashed with SHA-256 to produce `anchor_hash`.

Recording lifecycle:
1. `prepared` (payload + hash persisted offchain)
2. `submitted` (tx hash + block number captured)
3. `confirmed` (reserved status for receipt finalization flow in later phase)

## 4) Backend service for anchor preparation

New service: `app/services/anchoring.py`
- `prepare_anchor(...)` generates and stores the deterministic anchor hash
- `record_submitted_anchor(...)` records tx details after submit

API endpoints:
- `POST /api/v1/assets/{asset_id}/anchors/prepare`
- `POST /api/v1/assets/{asset_id}/anchors/{anchor_id}/record`

## 5) Chain/offchain consistency strategy

Consistency guarantees in this phase:
- one offchain anchor row per asset (`uq_asset_anchors_asset_id`)
- unique anchor hash globally (`uq_asset_anchors_anchor_hash`)
- optional unique tx hash (`uq_asset_anchors_tx_hash`)
- backend keeps explicit contract integration signatures in `app/blockchain/asset_registry_spec.py`
- tests assert Solidity source contains expected function + event signatures

This creates a verifiable link between internal asset fingerprint state and onchain commitment semantics.
