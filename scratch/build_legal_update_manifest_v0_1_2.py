"""
build_legal_update_manifest_v0_1_2.py
v0.1.1 대비 보정:
1. PDF manual 2건에 metadata_watch 분리 정책 적용
2. law_api_target=none 5건에 none_reason 필드 추가
3. source_refresh_method / metadata_watch_enabled 등 신규 필드 도입
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

# 지방계약 핵심 PDF 2건 title
PDF_METADATA_WATCH_TITLES = [
    "지방자치단체 입찰 및 계약집행기준",
    "지방자치단체 입찰시 낙찰자 결정기준"
]

def resolve_api_target(src_type, review_status):
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
    if api_target in ('law', 'admrul'):
        return 'law_api'
    if api_target == 'ordinance':
        return 'ordinance_manual'
    if src_type == 'pdf_manual':
        return 'pdf_manual'
    return 'institution_file'

def resolve_priority(active_rule, active_proc, review_status, src_type):
    if review_status in ('wrong_match', 'needs_manual_source'):
        return 'disabled'
    if src_type in ('ordinance', 'institution_rule'):
        return 'monthly'
    if src_type == 'pdf_manual':
        return 'monthly'  # full_text_refresh는 monthly
    if src_type == 'skip_api':
        return 'disabled'
    if active_rule or active_proc:
        return 'daily'
    if review_status in ('candidate_needs_review', 'needs_review'):
        return 'weekly'
    return 'monthly'

def resolve_none_reason(src_type, review_status, title):
    if review_status == 'wrong_match':
        return 'wrong_match_excluded'
    if review_status == 'needs_manual_source':
        return 'needs_manual_source_excluded'
    if src_type == 'pdf_manual':
        return 'pdf_manual_no_api_available'
    if src_type == 'skip_api':
        return 'skip_api_designated_by_collector'
    return 'unknown'

def resolve_recommended_action(src_type, review_status, title):
    if review_status in ('wrong_match', 'needs_manual_source'):
        return 'manual_review_required'
    if src_type == 'pdf_manual':
        return 'metadata_watch_via_official_url_weekly'
    if src_type == 'skip_api':
        return 'check_if_api_support_possible'
    return 'investigate'

manifest = []
none_reasons = []
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

    # PDF metadata watch 분리 정책
    is_pdf_metadata_watch = title in PDF_METADATA_WATCH_TITLES
    source_refresh_method = 'pdf_manual' if src_type == 'pdf_manual' else update_method
    metadata_watch_enabled = is_pdf_metadata_watch
    metadata_watch_frequency = 'weekly' if is_pdf_metadata_watch else None
    full_text_refresh_frequency = 'monthly' if src_type == 'pdf_manual' else None

    entry = {
        "source_id": source_id,
        "normalized_title": title,
        "source_type": src_type,
        "update_priority": priority,
        "update_method": update_method,
        "source_refresh_method": source_refresh_method,
        "metadata_watch_enabled": metadata_watch_enabled,
        "metadata_watch_frequency": metadata_watch_frequency,
        "full_text_refresh_frequency": full_text_refresh_frequency,
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
    }
    manifest.append(entry)

    # none reason report
    if api_target == 'none':
        none_reasons.append({
            "source_id": source_id,
            "normalized_title": title,
            "source_type": src_type,
            "review_status": review_status,
            "update_priority": priority,
            "none_reason": resolve_none_reason(src_type, review_status, title),
            "manual_review_required": manual_review_required,
            "recommended_update_action": resolve_recommended_action(src_type, review_status, title),
            "metadata_watch_enabled": metadata_watch_enabled,
            "official_url": official_url
        })

# Save manifest
with open(os.path.join(base, 'legal_update_manifest_v0_1_2.json'), 'w', encoding='utf-8') as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)

# Build report
api_dist = {}
for m in manifest:
    t = m["law_api_target"]
    api_dist[t] = api_dist.get(t, 0) + 1

metadata_watch_count = sum(1 for m in manifest if m["metadata_watch_enabled"])

report = {
    "title": "Legal Update Manifest Build Report v0.1.2",
    "build_date": datetime.datetime.now().isoformat(),
    "total_sources": counts["total"],
    "distribution": counts,
    "law_api_target_distribution": api_dist,
    "metadata_watch_enabled_count": metadata_watch_count,
    "pdf_metadata_watch_targets": PDF_METADATA_WATCH_TITLES
}
with open(os.path.join(base, 'legal_update_manifest_build_report_v0_1_2.json'), 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

# None reason report
none_report = {
    "title": "None Target Reason Report v0.1.2",
    "total_none_targets": len(none_reasons),
    "items": none_reasons
}
with open(os.path.join(base, 'none_target_reason_report_v0_1_2.json'), 'w', encoding='utf-8') as f:
    json.dump(none_report, f, ensure_ascii=False, indent=2)

conn.close()
print("Manifest v0.1.2 built successfully.")
print(json.dumps(report, indent=2, ensure_ascii=False))
print(f"\nNone targets: {len(none_reasons)}")
print(f"Metadata watch targets: {metadata_watch_count}")
