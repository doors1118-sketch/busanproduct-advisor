CREATE TABLE legal_interpretation_impact_queue (
    queue_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    impact_level TEXT,
    affected_activation_mode TEXT,
    affected_required_slots TEXT,
    requires_rule_review BOOLEAN,
    review_status TEXT,
    created_at TEXT,
    resolved_at TEXT
);
