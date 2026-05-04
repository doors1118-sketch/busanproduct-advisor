-- Phase 7-B v0.1.1 Seed Mapping Table
-- This table preserves seed definitions and aliases for legal sources that were merged
-- into a single canonical source due to identical normalized_titles.

CREATE TABLE IF NOT EXISTS legal_source_seed_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    seed_id VARCHAR(255),
    original_query VARCHAR(512),
    original_node_name VARCHAR(512),
    canonical_source_id VARCHAR(36) NOT NULL,
    mapping_type VARCHAR(100) NOT NULL, -- e.g., 'alias', 'patch_origin', 'duplicate'
    review_status VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (canonical_source_id) REFERENCES legal_source(source_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_lssm_canonical ON legal_source_seed_mapping(canonical_source_id);
CREATE INDEX IF NOT EXISTS idx_lssm_seed ON legal_source_seed_mapping(seed_id);
