import sqlite3, json, os, datetime
sys_stdout = os.sys.stdout

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
db_path = os.path.join(base, 'legal_db_v0_1_3.sqlite')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Get all sources
cur.execute("""
    SELECT source_id, normalized_title, source_type, review_status, 
           active_for_rule, active_for_procedure, activation_mode,
           official_url, version_hash
    FROM legal_source
""")
rows = cur.fetchall()

manifest = []
counts = {
    "total": 0,
    "daily": 0,
    "weekly": 0,
    "monthly_manual": 0,
    "inactive": 0
}

for row in rows:
    counts["total"] += 1
    (source_id, title, src_type, review_status, active_rule, active_proc, act_mode, official_url, version_hash) = row
     
    active_rule = bool(active_rule)
    active_proc = bool(active_proc)
    
    # Priority
    priority = "manual"
    update_enabled = True
    manual_review_required = False
    
    if review_status == 'wrong_match':
        update_enabled = False
        manual_review_required = True
        priority = "inactive"
        counts["inactive"] += 1
    elif review_status == 'needs_manual_source' or src_type in ['ordinance', 'institution_rule', 'pdf_manual']:
        priority = "monthly"
        if review_status == 'needs_manual_source':
            update_enabled = False
            manual_review_required = True
            priority = "inactive"
            counts["inactive"] += 1
        else:
            counts["monthly_manual"] += 1
    elif active_rule or active_proc:
        priority = "daily"
        counts["daily"] += 1
    elif review_status in ['candidate_needs_review', 'needs_review']:
        priority = "weekly"
        counts["weekly"] += 1
    else:
        # fallback
        priority = "monthly"
        counts["monthly_manual"] += 1

    # Law API Target
    law_api_target = src_type in ['law', 'enforcement_decree', 'enforcement_rule', 'administrative_rule']
    if priority == "inactive":
        law_api_target = False
        
    update_method = "law_api" if law_api_target else ("pdf_manual" if src_type == "pdf_manual" else ("ordinance_manual" if src_type == "ordinance" else "institution_file"))
    
    watch_fields = ["effective_date", "amended_date", "promulgation_no", "full_text_hash"]
    
    manifest_item = {
        "source_id": source_id,
        "normalized_title": title,
        "source_type": src_type,
        "update_priority": priority,
        "update_method": update_method,
        "law_api_target": law_api_target,
        "law_id": None,
        "mst": None,
        "admrul_seq": None,
        "official_url": official_url,
        "source_file_path": None,
        "source_file_hash": None,
        "active_for_rule": active_rule,
        "active_for_procedure": active_proc,
        "activation_mode": act_mode,
        "current_version_hash": version_hash if version_hash else "mock_hash_base",
        "last_checked_at": None,
        "last_successful_checked_at": None,
        "last_error_message": None,
        "update_enabled": update_enabled,
        "manual_review_required": manual_review_required,
        "watch_fields": watch_fields
    }
    manifest.append(manifest_item)

# Save manifest
manifest_path = os.path.join(base, 'legal_update_manifest.json')
with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

# Save report
report = {
    "title": "Legal Update Manifest Build Report v0.1",
    "total_sources": counts["total"],
    "distribution": counts
}
report_path = os.path.join(base, 'legal_update_manifest_build_report.json')
with open(report_path, 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

conn.close()
print("Manifest built successfully.")
print(json.dumps(report, indent=2))
