CREATE TABLE direct_production_requirement (
    requirement_id TEXT PRIMARY KEY,
    detail_item_code TEXT NOT NULL,
    direct_production_required BOOLEAN NOT NULL DEFAULT 1,
    direct_production_standard_source_id TEXT, -- Foreign key linking to legal_source
    standard_article_ref TEXT, -- E.g. "제5조"
    required_facility_or_process_summary TEXT,
    effective_from TEXT,
    effective_to TEXT,
    version_hash TEXT,
    review_status TEXT DEFAULT 'pending',
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
