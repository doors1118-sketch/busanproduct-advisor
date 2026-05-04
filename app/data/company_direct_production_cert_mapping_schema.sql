CREATE TABLE company_direct_production_cert_mapping (
    company_id TEXT NOT NULL,
    detail_item_code TEXT NOT NULL,
    cert_status TEXT NOT NULL, -- e.g., 'valid', 'expired', 'revoked'
    valid_from TEXT,
    valid_to TEXT,
    source TEXT, -- Origin of the certificate data
    pii_sanitized BOOLEAN NOT NULL DEFAULT 1, -- Must be 1 (true) indicating no personal/business numbers are included
    PRIMARY KEY (company_id, detail_item_code),
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
