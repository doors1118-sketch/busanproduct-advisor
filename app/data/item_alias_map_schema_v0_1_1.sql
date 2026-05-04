CREATE TABLE item_alias_map (
    alias_id TEXT PRIMARY KEY,
    alias_name TEXT NOT NULL,
    detail_item_code TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    alias_type TEXT, -- e.g., 'common_name', 'slang', 'acronym'
    match_confidence REAL DEFAULT 1.0,
    display_rank INTEGER DEFAULT 1,
    source TEXT,
    review_status TEXT DEFAULT 'pending',
    FOREIGN KEY (detail_item_code) REFERENCES procurement_item_master(detail_item_code)
);
