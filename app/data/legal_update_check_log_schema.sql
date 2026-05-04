CREATE TABLE legal_update_check_log (
    check_id TEXT PRIMARY KEY,
    checked_at TEXT NOT NULL,
    source_id TEXT,
    check_type TEXT,
    result TEXT,
    error_message TEXT
);
