CREATE TABLE assets (
    id TEXT PRIMARY KEY,
    owner TEXT,
    asset_type TEXT,
    location TEXT,
    metadata JSON,
    created_at TIMESTAMP
);