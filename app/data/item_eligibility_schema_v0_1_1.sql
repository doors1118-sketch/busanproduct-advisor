CREATE TABLE procurement_item_master (
    item_id TEXT PRIMARY KEY,
    item_name TEXT NOT NULL,
    item_aliases TEXT, -- JSON array of strings
    g2b_category_code TEXT,
    detail_item_code TEXT NOT NULL UNIQUE,
    detail_item_name TEXT NOT NULL,
    review_status TEXT DEFAULT 'pending'
);
