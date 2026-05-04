"""
build_legal_update_manifest_v0_1_1.py
법령DB v0.1.3에서 217건을 읽어 정규 Manifest를 생성한다.
law_api_target을 boolean에서 enum(law/admrul/ordinance/none)으로 전환한다.
"""
import sqlite3, json, os, datetime

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
db_path = os.path.join(base, 'legal_db_v0_1_3.sqlite')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("""
    SELECT source_id, normalized_title, source_type, review_status,
           active_for_rule, active_for_procedure, activation_mode,
           official_url, version_hash
    FROM legal_source
""")
rows = cur.fetchall()

# source_type → law_api_target enum 매핑
def resolve_api_target(src_type, review_status):
    """source_type에 따라 법제처 API adapter 유형을 결정한다."""
    if review_status in ('wrong_match', 'needs_manual_source'):
        return 'none'
    if src_type in ('law', 'law_decree', 'law_rule'):
        return 'law'
    if src_type in ('admrul', 'admrul_instruction', 'admrul_notice', 'admrul_regulation'):
        return 'admrul'
    if src_type in ('ordinance',):
        return 'ordinance'
    if src_type in ('pdf_manual', 'skip_api'):
        return 'none'
    return 'none'

def resolve_update_method(api_target, src_type):
    if api_target == 'law':
        return 'law_api'
    if api_target == 'admrul':
        return 'law_api'
    if api_target == 'ordinance':
        return 'ordinance_manual'
    if src_type == 'pdf_manual':
        return 'pdf_manual'
    return 'institution_file'

def resolve_priority(active_rule, active_proc, review_status, src_type):
    if review_status in ('wrong_match', 'needs_manual_source'):
        return 'disabled'
    if src_type in ('ordinance', 'institution_rule', 'pdf_manual'):
        return 'monthly'
    if active_rule or active_proc:
        return 'daily'
    if review_status in ('candidate_needs_review', 'needs_review'):
        return 'weekly'
    return 'monthly'

manifest = []
counts = {"total": 0, "daily": 0, "weekly": 0, "monthly": 0, "manual": 0, "disabled": 0}

for row in rows:
    counts["total"] += 1
    (source_id, title, src_type, review_status, active_rule, active_proc,
     act_mode, official_url, version_hash) = row

    active_rule = bool(active_rule)
    active_proc = bool(active_proc)

    priority = resolve_priority(active_rule, active_proc, review_status, src_type)
    api_target = resolve_api_target(src_type, review_status)
    update_method = resolve_update_method(api_target, src_type)

    update_enabled = priority != 'disabled'
    manual_review_required = review_status in ('wrong_match', 'needs_manual_source')

    counts[priority] = counts.get(priority, 0) + 1

    manifest.append({
        "source_id": source_id,
        "normalized_title": title,
        "source_type": src_type,
        "update_priority": priority,
        "update_method": update_method,
        "law_api_target": api_target,
        "law_id": None,
        "mst": None,
        "admrul_seq": None,
        "official_url": official_url,
        "source_file_path": None,
        "source_file_hash": None,
        "active_for_rule": active_rule,
        "active_for_procedure": active_proc,
        "activation_mode": act_mode,
        "current_version_hash": version_hash if version_hash else None,
        "last_checked_at": None,
        "last_successful_checked_at": None,
        "last_error_message": None,
        "update_enabled": update_enabled,
        "manual_review_required": manual_review_required,
        "watch_fields": ["effective_date", "amended_date", "promulgation_no", "full_text_hash"]
    })

with open(os.path.join(base, 'legal_update_manifest_v0_1_1.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

report = {
    "title": "Legal Update Manifest Build Report v0.1.1",
    "build_date": datetime.datetime.now().isoformat(),
    "total_sources": counts["total"],
    "distribution": counts,
    "law_api_target_distribution": {}
}
for m in manifest:
    t = m["law_api_target"]
    report["law_api_target_distribution"][t] = report["law_api_target_distribution"].get(t, 0) + 1

with open(os.path.join(base, 'legal_update_manifest_build_report_v0_1_1.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

conn.close()
print("Manifest v0.1.1 built successfully.")
print(json.dumps(report, indent=2, ensure_ascii=False))
