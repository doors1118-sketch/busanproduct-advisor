-- Phase 7-B Master Registry DB Schema (SQLite dialect for simulation)
-- 1. Main Legal Source Table
CREATE TABLE IF NOT EXISTS legal_source (
    source_id VARCHAR(36) PRIMARY KEY,
    seed_id VARCHAR(255),
    source_name VARCHAR(512) NOT NULL,
    normalized_title VARCHAR(512) UNIQUE NOT NULL,
    law_category VARCHAR(100),
    source_type VARCHAR(100),
    relation_type VARCHAR(100),
    applicability_scope VARCHAR(100),
    review_status VARCHAR(100) NOT NULL,
    registry_trust_level VARCHAR(100) NOT NULL,
    confidence VARCHAR(50),
    effective_date VARCHAR(50),
    official_url TEXT,
    version_hash VARCHAR(100),
    active_for_rule BOOLEAN NOT NULL,
    article_count INTEGER DEFAULT 0,
    full_text_length INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Jurisdiction Mapping Table (N:M)
CREATE TABLE IF NOT EXISTS legal_jurisdiction_mapping (
    source_id VARCHAR(36) NOT NULL,
    jurisdiction_scope VARCHAR(100) NOT NULL,
    PRIMARY KEY (source_id, jurisdiction_scope),
    FOREIGN KEY (source_id) REFERENCES legal_source(source_id) ON DELETE CASCADE
);

-- 3. Buyer Type Mapping Table (N:M)
CREATE TABLE IF NOT EXISTS legal_buyer_type_mapping (
    source_id VARCHAR(36) NOT NULL,
    buyer_type_scope VARCHAR(100) NOT NULL,
    PRIMARY KEY (source_id, buyer_type_scope),
    FOREIGN KEY (source_id) REFERENCES legal_source(source_id) ON DELETE CASCADE
);

-- 4. Overlay Mapping Table (N:M)
CREATE TABLE IF NOT EXISTS legal_overlay_mapping (
    source_id VARCHAR(36) NOT NULL,
    overlay_scope VARCHAR(100) NOT NULL,
    PRIMARY KEY (source_id, overlay_scope),
    FOREIGN KEY (source_id) REFERENCES legal_source(source_id) ON DELETE CASCADE
);

-- 5. Legal Relations Table
CREATE TABLE IF NOT EXISTS legal_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_title VARCHAR(512) NOT NULL,
    target_title VARCHAR(512) NOT NULL,
    relation_type VARCHAR(100) NOT NULL,
    application_condition TEXT,
    confidence VARCHAR(50) DEFAULT 'high',
    review_status VARCHAR(100) DEFAULT 'verified'
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ls_review_status ON legal_source(review_status);
CREATE INDEX IF NOT EXISTS idx_ls_trust_level ON legal_source(registry_trust_level);
CREATE INDEX IF NOT EXISTS idx_ls_active_rule ON legal_source(active_for_rule);
CREATE INDEX IF NOT EXISTS idx_lr_source ON legal_relation(source_title);
CREATE INDEX IF NOT EXISTS idx_lr_target ON legal_relation(target_title);
