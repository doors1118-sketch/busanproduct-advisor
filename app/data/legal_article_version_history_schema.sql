CREATE TABLE legal_article_version_history (
    article_version_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    article_no TEXT,
    old_article_hash TEXT,
    new_article_hash TEXT,
    change_type TEXT,
    diff_summary TEXT
);
