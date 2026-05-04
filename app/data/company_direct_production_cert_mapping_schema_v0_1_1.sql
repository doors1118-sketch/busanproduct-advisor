CREATE TABLE company_direct_production_cert_mapping (
    cert_mapping_id TEXT PRIMARY KEY,
    company_id TEXT NOT NULL,
    detail_item_code TEXT NOT NULL,
    cert_status TEXT NOT NULL, -- e.g., 'valid', 'expired', 'revoked'
    valid_from TEXT,
    valid_to TEXT,
    source TEXT, -- Origin of the certificate data
    pii_sanitized BOOLEAN NOT NULL DEFAULT 1, -- Must be 1 (true)
    cert_number_hash TEXT, -- Store hash only, no original cert number
    business_number_hash TEXT, -- Store hash only, no original business number
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
