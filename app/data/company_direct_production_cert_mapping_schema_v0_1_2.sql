CREATE TABLE company_direct_production_cert_mapping (
    cert_mapping_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    detail_item_code TEXT NOT NULL,
    detail_item_name TEXT,
    cert_status TEXT NOT NULL DEFAULT 'unknown', -- valid, expired, revoked, unknown
    valid_from TEXT,
    valid_to TEXT,
    source TEXT,
    source_checked_at TEXT,
    cert_hash TEXT,
    pii_sanitized BOOLEAN NOT NULL DEFAULT 1,
    version_hash TEXT,
    review_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
