"""
diff_legal_versions_v0_1_1.py
Old/New article hash 비교 구조를 설계한다.
아직 원문 재수집이 없으므로 diff는 skipped 처리한다.
"""
import json, os, datetime

def generate_diff(source_id, title, old_hash, new_hash):
    """
    실제 diff 엔진 인터페이스.
    old_hash와 new_hash가 모두 존재하고 다를 때만 diff를 수행한다.
    현재 단계에서는 new_hash가 없으므로 모든 항목이 skipped된다.
    """
    if new_hash is None or old_hash is None:
        return {
            "source_id": source_id,
            "title": title,
            "diff_status": "skipped",
            "reason": "new_version_not_available",
            "old_version_hash": old_hash,
            "new_version_hash": new_hash,
            "diff_type": None,
            "changed_articles": [],
            "added_articles": [],
            "deleted_articles": []
        }

    if old_hash == new_hash:
        return {
            "source_id": source_id,
            "title": title,
            "diff_status": "unchanged",
            "reason": "hash_match",
            "old_version_hash": old_hash,
            "new_version_hash": new_hash,
            "diff_type": "none",
            "changed_articles": [],
            "added_articles": [],
            "deleted_articles": []
        }

    # 실제 diff 수행 (향후 구현)
    return {
        "source_id": source_id,
        "title": title,
        "diff_status": "changed",
        "reason": "hash_mismatch",
        "old_version_hash": old_hash,
        "new_version_hash": new_hash,
        "diff_type": "article_text_changed",
        "changed_articles": [],
        "added_articles": [],
        "deleted_articles": []
    }


def run_diff_dry_run(manifest_path):
    """Manifest의 daily 대상에 대해 diff dry-run을 수행한다."""
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    daily = [m for m in manifest if m["update_priority"] == "daily" and m["update_enabled"]]

    results = []
    for m in daily:
        result = generate_diff(
            m["source_id"],
            m["normalized_title"],
            m["current_version_hash"],
            None  # 아직 원문 재수집이 없으므로 new_hash는 None
        )
        results.append(result)

    skipped_count = sum(1 for r in results if r["diff_status"] == "skipped")

    report = {
        "title": "Legal Diff Skipped Report v0.1.1",
        "run_date": datetime.datetime.now().isoformat(),
        "total_targets": len(results),
        "skipped": skipped_count,
        "unchanged": sum(1 for r in results if r["diff_status"] == "unchanged"),
        "changed": sum(1 for r in results if r["diff_status"] == "changed"),
        "note": "원문 재수집이 수행되지 않았으므로 모든 diff가 skipped 처리되었습니다."
    }

    return report, results


if __name__ == "__main__":
    base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
    manifest_path = os.path.join(base, 'legal_update_manifest_v0_1_1.json')
    report, _ = run_diff_dry_run(manifest_path)
    out_path = os.path.join(base, 'legal_diff_skipped_report_v0_1_1.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Diff dry-run complete. Skipped={report['skipped']}, Changed={report['changed']}")
