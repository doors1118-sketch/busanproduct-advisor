import json, sqlite3, sys, os
sys.stdout.reconfigure(encoding='utf-8')

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
db_path = os.path.join(base, 'legal_db_v0_1.sqlite')
schema_path = os.path.join(base, 'legal_db_schema.sql')
mapping_schema_path = os.path.join(base, 'legal_source_seed_mapping_schema.sql')

candidate_path = os.path.join(base, 'legal_source_registry_master_by_jurisdiction_v0_1_candidate.json')
relations_path = os.path.join(base, 'legal_relation_seed_by_jurisdiction_v0_1.json')

def run_import():
    if os.path.exists(db_path):
        os.remove(db_path)
        
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('PRAGMA foreign_keys = ON;')
    
    # 1. Initialize Schema
    with open(schema_path, encoding='utf-8') as f:
        cur.executescript(f.read())
    with open(mapping_schema_path, encoding='utf-8') as f:
        cur.executescript(f.read())
        
    # 2. Load JSON Data
    with open(candidate_path, encoding='utf-8') as f:
        sources = json.load(f)
        
    with open(relations_path, encoding='utf-8') as f:
        relations = json.load(f)
        
    # Deduplication Logic
    canonical_sources = {}
    dedup_explanation = []
    
    for s in sources:
        norm = s.get('normalized_title')
        if norm in canonical_sources:
            # Existing item is canonical. The current item `s` is a duplicate/alias.
            canonical = canonical_sources[norm]
            dedup_explanation.append({
                "normalized_title": norm,
                "canonical_source_id": canonical['source_id'],
                "canonical_seed_id": canonical.get('seed_id'),
                "merged_alias_seed_id": s.get('seed_id'),
                "merged_source_name": s.get('source_name'),
                "reason": "Exact match on normalized_title"
            })
            # Save the alias info to be inserted later
            canonical.setdefault('_aliases', []).append(s)
        else:
            canonical_sources[norm] = s

    # 3. Insert Legal Sources
    for norm, s in canonical_sources.items():
        sid = s.get('source_id')
        review_status = s.get('review_status')
        trust_level = s.get('registry_trust_level')
        
        # Correct Active For Rule Logic
        active = (
            review_status == "verified"
            and trust_level in ["core_verified", "verified", "conditional_verified"]
        )
            
        cur.execute('''
            INSERT INTO legal_source (
                source_id, seed_id, source_name, normalized_title, law_category, 
                source_type, relation_type, applicability_scope, review_status, 
                registry_trust_level, confidence, effective_date, official_url, 
                version_hash, active_for_rule, article_count, full_text_length
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            sid, s.get('seed_id'), s.get('source_name'), s.get('normalized_title'),
            s.get('law_category'), s.get('source_type'), s.get('relation_type'),
            s.get('applicability_scope'), review_status, trust_level,
            s.get('confidence'), s.get('effective_date'), s.get('official_url'),
            s.get('version_hash'), active, s.get('article_count', 0), s.get('full_text_length', 0)
        ))
        
        # Mapping for canonical seed itself (optional but good for completeness if seed_id exists)
        if s.get('seed_id'):
            cur.execute('''
                INSERT INTO legal_source_seed_mapping (
                    seed_id, original_query, original_node_name, canonical_source_id, mapping_type, review_status
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (s.get('seed_id'), s.get('name'), s.get('source_name'), sid, 'canonical', review_status))

        # Insert aliases into mapping table
        for alias in s.get('_aliases', []):
            cur.execute('''
                INSERT INTO legal_source_seed_mapping (
                    seed_id, original_query, original_node_name, canonical_source_id, mapping_type, review_status
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                alias.get('seed_id'), alias.get('name'), alias.get('source_name'), 
                sid, 'duplicate_alias', alias.get('review_status')
            ))
            # Merge scopes from aliases into canonical
            s.setdefault('jurisdiction_scope', []).extend(alias.get('jurisdiction_scope', []))
            s.setdefault('buyer_type_scope', []).extend(alias.get('buyer_type_scope', []))
            s.setdefault('overlay_scope', []).extend(alias.get('overlay_scope', []))
        
        # Insert Jurisdiction Mappings
        for j in set(s.get('jurisdiction_scope', [])):
            cur.execute('INSERT OR IGNORE INTO legal_jurisdiction_mapping (source_id, jurisdiction_scope) VALUES (?, ?)', (sid, j))
            
        # Insert Buyer Type Mappings
        for b in set(s.get('buyer_type_scope', [])):
            cur.execute('INSERT OR IGNORE INTO legal_buyer_type_mapping (source_id, buyer_type_scope) VALUES (?, ?)', (sid, b))
            
        # Insert Overlay Mappings
        for o in set(s.get('overlay_scope', [])):
            cur.execute('INSERT OR IGNORE INTO legal_overlay_mapping (source_id, overlay_scope) VALUES (?, ?)', (sid, o))
            
    # 4. Insert Relations
    for r in relations:
        cur.execute('''
            INSERT INTO legal_relation (
                source_title, target_title, relation_type, application_condition, confidence, review_status
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            r.get('source'), r.get('target'), r.get('relation_type'),
            r.get('application_condition'), r.get('confidence', 'high'), r.get('review_status', 'verified')
        ))
        
    conn.commit()
    print("Database population completed successfully.")
    
    # 5. Validation Report
    validation_report = {
        "title": "Legal DB Import Validation Report v0.1.1",
        "total_sources_inserted": cur.execute("SELECT COUNT(*) FROM legal_source").fetchone()[0],
        "total_seed_mappings": cur.execute("SELECT COUNT(*) FROM legal_source_seed_mapping").fetchone()[0],
        "total_jurisdiction_mappings": cur.execute("SELECT COUNT(*) FROM legal_jurisdiction_mapping").fetchone()[0],
        "total_buyer_type_mappings": cur.execute("SELECT COUNT(*) FROM legal_buyer_type_mapping").fetchone()[0],
        "total_overlay_mappings": cur.execute("SELECT COUNT(*) FROM legal_overlay_mapping").fetchone()[0],
        "total_relations": cur.execute("SELECT COUNT(*) FROM legal_relation").fetchone()[0],
        "integrity_checks": {
            "orphan_jurisdictions": cur.execute("SELECT COUNT(*) FROM legal_jurisdiction_mapping WHERE source_id NOT IN (SELECT source_id FROM legal_source)").fetchone()[0],
            "orphan_buyers": cur.execute("SELECT COUNT(*) FROM legal_buyer_type_mapping WHERE source_id NOT IN (SELECT source_id FROM legal_source)").fetchone()[0],
            "orphan_overlays": cur.execute("SELECT COUNT(*) FROM legal_overlay_mapping WHERE source_id NOT IN (SELECT source_id FROM legal_source)").fetchone()[0],
            "orphan_seed_mappings": cur.execute("SELECT COUNT(*) FROM legal_source_seed_mapping WHERE canonical_source_id NOT IN (SELECT source_id FROM legal_source)").fetchone()[0]
        }
    }
    
    with open(os.path.join(base, 'legal_import_validation_report_v0_1_2.json'), 'w', encoding='utf-8') as f:
        json.dump(validation_report, f, ensure_ascii=False, indent=2)
        
    # 6. Active Filter Report
    active_true = cur.execute("SELECT normalized_title, registry_trust_level FROM legal_source WHERE active_for_rule = 1").fetchall()
    active_false = cur.execute("SELECT normalized_title, review_status, registry_trust_level FROM legal_source WHERE active_for_rule = 0").fetchall()
    
    filter_report = {
        "title": "Active For Rule Filter Report v0.1.2",
        "active_true_count": len(active_true),
        "active_false_count": len(active_false),
        "active_true_samples": [{"title": r[0], "trust_level": r[1]} for r in active_true[:10]],
        "active_false_details": [{"title": r[0], "reason": f"review_status={r[1]}, trust_level={r[2]}"} for r in active_false]
    }
    
    with open(os.path.join(base, 'active_for_rule_filter_report_v0_1_2.json'), 'w', encoding='utf-8') as f:
        json.dump(filter_report, f, ensure_ascii=False, indent=2)
        
    # 7. Dedup Explanation Report
    with open(os.path.join(base, 'legal_source_dedup_explanation_report.json'), 'w', encoding='utf-8') as f:
        json.dump({
            "title": "Legal Source Deduplication Explanation",
            "total_candidates": len(sources),
            "total_canonical": len(canonical_sources),
            "merged_duplicates_count": len(dedup_explanation),
            "details": dedup_explanation
        }, f, ensure_ascii=False, indent=2)
        
    print("Reports generated successfully.")
    conn.close()

if __name__ == '__main__':
    run_import()
