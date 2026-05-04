CREATE TABLE sme_competition_product_item (
    designation_id TEXT PRIMARY KEY,
    detail_item_code TEXT NOT NULL,
    detail_item_name TEXT NOT NULL,
    is_sme_competition_product BOOLEAN NOT NULL DEFAULT 1,
    designation_source_id TEXT,
    source_document_name TEXT,
    effective_from TEXT,
    effective_to TEXT,
    version_hash TEXT,
    review_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
