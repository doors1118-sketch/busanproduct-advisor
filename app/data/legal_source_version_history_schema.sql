CREATE TABLE legal_source_version_history (
    version_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    old_version_hash TEXT,
    new_version_hash TEXT,
    effective_date TEXT,
    amended_date TEXT,
    checked_at TEXT,
    update_status TEXT,
    change_summary TEXT
);
