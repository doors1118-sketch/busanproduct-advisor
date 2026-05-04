CREATE TABLE direct_production_requirement (
    requirement_id TEXT PRIMARY KEY,
    detail_item_code TEXT NOT NULL,
    detail_item_name TEXT,
    direct_production_required BOOLEAN NOT NULL DEFAULT 1,
    direct_production_standard_source_id TEXT,
    standard_article_ref TEXT,
    required_facility_summary TEXT,
    required_process_summary TEXT,
    effective_from TEXT,
    effective_to TEXT,
    version_hash TEXT,
    review_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
