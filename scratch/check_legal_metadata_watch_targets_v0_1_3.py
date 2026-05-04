"""
check_legal_metadata_watch_targets_v0_1_3.py
metadata_watch_enabled=true 대상을 별도 실행 큐로 분리한다.
update_priority=monthly여도 metadata_watch_frequency=weekly이면
weekly metadata watch queue에 포함한다.
실제 URL 접속은 수행하지 않는다.
"""
import json, os, datetime

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

def build_metadata_watch_queue(manifest_path):
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    watch_targets = [m for m in manifest if m.get("metadata_watch_enabled")]

    queue = []
    for t in watch_targets:
        entry = {
            "source_id": t["source_id"],
            "normalized_title": t["normalized_title"],
            "source_type": t["source_type"],
            "update_priority": t["update_priority"],
            "metadata_watch_frequency": t.get("metadata_watch_frequency"),
            "full_text_refresh_frequency": t.get("full_text_refresh_frequency"),
            "active_for_rule": t["active_for_rule"],
            "active_for_procedure": t["active_for_procedure"],
            "activation_mode": t.get("activation_mode"),
            "official_url": t.get("official_url"),
            "law_api_target": t["law_api_target"],
            "source_refresh_method": t.get("source_refresh_method"),
            "current_version_hash": t.get("current_version_hash"),
            "watch_status": "pending_dry_run",
            "last_metadata_check": None,
            "metadata_changed": None,
            "note": "dry_run 모드 — 실제 URL 접속 미수행"
        }
        queue.append(entry)

    return queue


def build_report(queue):
    report = {
        "title": "Legal Metadata Watch Targets Report v0.1.3",
        "report_date": datetime.datetime.now().isoformat(),
        "mode": "dry_run",
        "metadata_watch_targets_count": len(queue),
        "all_active_for_rule": all(t["active_for_rule"] for t in queue),
        "all_metadata_watch_weekly": all(t["metadata_watch_frequency"] == "weekly" for t in queue),
        "all_full_text_monthly": all(t["full_text_refresh_frequency"] == "monthly" for t in queue),
        "update_priority_distribution": {},
        "targets": queue,
        "blocked_operations": [
            "실제 URL 접속",
            "실제 원문 재수집",
            "DB patch 적용",
            "scheduler 등록",
            "Production 배포"
        ]
    }
    for t in queue:
        p = t["update_priority"]
        report["update_priority_distribution"][p] = report["update_priority_distribution"].get(p, 0) + 1

    return report


if __name__ == "__main__":
    manifest_path = os.path.join(base, 'legal_update_manifest_v0_1_2.json')
    queue = build_metadata_watch_queue(manifest_path)
    report = build_report(queue)

    out_path = os.path.join(base, 'legal_metadata_watch_targets_report_v0_1_3.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"Metadata watch targets: {report['metadata_watch_targets_count']}")
    print(f"All active_for_rule: {report['all_active_for_rule']}")
    print(f"All weekly: {report['all_metadata_watch_weekly']}")
    print(f"All monthly full_text: {report['all_full_text_monthly']}")
    print(f"Priority distribution: {report['update_priority_distribution']}")
    for t in queue:
        print(f"  [{t['update_priority']:10s}] {t['normalized_title']}")
