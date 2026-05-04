CREATE TABLE procurement_item_master (
    item_id TEXT PRIMARY KEY,
    detail_item_code TEXT NOT NULL UNIQUE,
    detail_item_name TEXT NOT NULL,
    item_name TEXT,
    item_group_name TEXT,
    g2b_category_code TEXT,
    g2b_category_name TEXT,
    source TEXT,
    source_version TEXT,
    version_hash TEXT,
    effective_from TEXT,
    effective_to TEXT,
    review_status TEXT DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
