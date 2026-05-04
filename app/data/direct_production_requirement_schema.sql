CREATE TABLE direct_production_requirement (
    item_id TEXT PRIMARY KEY,
    detail_item_code TEXT NOT NULL,
    direct_production_required BOOLEAN NOT NULL DEFAULT 1,
    direct_production_standard_source_id TEXT, -- Foreign key linking to legal_source
    required_facility_or_process_summary TEXT,
    review_status TEXT DEFAULT 'pending',
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
