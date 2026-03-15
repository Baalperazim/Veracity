// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

/// @title Veracity AssetRegistry (Phase 3)
/// @notice Minimal immutable anchor registry for verified offchain assets.
contract AssetRegistry {
    address public immutable owner;

    struct AssetAnchor {
        bytes32 assetId;
        bytes32 anchorHash;
        string anchorURI;
        address recorder;
        uint64 anchoredAt;
    }

    mapping(bytes32 => AssetAnchor) private anchors;

    /// @custom:signature AssetAnchored(bytes32,bytes32,string,address)
    event AssetAnchored(bytes32 indexed assetId, bytes32 indexed anchorHash, string anchorURI, address indexed recorder);

    error NotOwner();
    error AlreadyAnchored(bytes32 assetId);

    constructor(address owner_) {
        owner = owner_;
    }

    /// @custom:signature anchorAsset(bytes32,bytes32,string)
    /// @notice Stores the first anchor for an offchain asset id.
    /// @dev This contract intentionally supports one immutable anchor per asset in Phase 3.
    function anchorAsset(bytes32 assetId, bytes32 anchorHash, string calldata anchorURI) external {
        if (msg.sender != owner) revert NotOwner();
        if (anchors[assetId].anchoredAt != 0) revert AlreadyAnchored(assetId);

        anchors[assetId] = AssetAnchor({
            assetId: assetId,
            anchorHash: anchorHash,
            anchorURI: anchorURI,
            recorder: msg.sender,
            anchoredAt: uint64(block.timestamp)
        });

        emit AssetAnchored(assetId, anchorHash, anchorURI, msg.sender);
    }

    function getAnchor(bytes32 assetId) external view returns (AssetAnchor memory) {
        return anchors[assetId];
    }
}
