CREATE TABLE legal_release_manifest (
    release_id TEXT PRIMARY KEY,
    db_version TEXT,
    source_patch_count INTEGER,
    article_patch_count INTEGER,
    interpretation_patch_count INTEGER,
    active_for_rule_count INTEGER,
    active_for_procedure_count INTEGER,
    created_at TEXT,
    release_status TEXT
);
