"""
check_legal_source_updates_v0_1_1.py
Manifest를 읽어 priority별 대상 목록을 분류한다.
실제 API 호출 없이, dry_run 모드에서는 조회 대상 목록만 생성한다.
임의로 changed를 만들지 않는다.
"""
import json, os, datetime

def check_updates(manifest_path, mode="dry_run"):
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    targets = {
        "daily_targets": [],
        "weekly_targets": [],
        "monthly_targets": [],
        "manual_targets": [],
        "disabled_targets": []
    }

    for m in manifest:
        entry = {
            "source_id": m["source_id"],
            "normalized_title": m["normalized_title"],
            "source_type": m["source_type"],
            "law_api_target": m["law_api_target"],
            "update_method": m["update_method"],
            "active_for_rule": m["active_for_rule"],
            "active_for_procedure": m["active_for_procedure"],
            "activation_mode": m["activation_mode"],
            "current_version_hash": m["current_version_hash"],
            "update_enabled": m["update_enabled"]
        }

        p = m["update_priority"]
        if p == "daily":
            targets["daily_targets"].append(entry)
        elif p == "weekly":
            targets["weekly_targets"].append(entry)
        elif p == "monthly":
            targets["monthly_targets"].append(entry)
        elif p == "manual":
            targets["manual_targets"].append(entry)
        elif p == "disabled":
            targets["disabled_targets"].append(entry)

    # Adapter readiness per target
    adapter_readiness = {
        "law": {"adapter_available": True, "mode": "dry_run_only"},
        "admrul": {"adapter_available": True, "mode": "dry_run_only"},
        "ordinance": {"adapter_available": False, "mode": "manual_only"},
        "none": {"adapter_available": False, "mode": "not_applicable"}
    }

    report = {
        "title": "Legal Update Check Targets Report v0.1.1",
        "check_date": datetime.datetime.now().isoformat(),
        "mode": mode,
        "note": "dry_run 모드에서는 실제 API 호출과 변경 감지를 수행하지 않습니다. 조회 대상 분류만 수행합니다.",
        "summary": {
            "daily_count": len(targets["daily_targets"]),
            "weekly_count": len(targets["weekly_targets"]),
            "monthly_count": len(targets["monthly_targets"]),
            "manual_count": len(targets["manual_targets"]),
            "disabled_count": len(targets["disabled_targets"])
        },
        "adapter_readiness": adapter_readiness,
        "targets": targets
    }

    return report

if __name__ == "__main__":
    base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
    manifest_path = os.path.join(base, 'legal_update_manifest_v0_1_1.json')
    report = check_updates(manifest_path, mode="dry_run")
    out_path = os.path.join(base, 'legal_update_check_targets_report_v0_1_1.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Check targets report generated. Daily={report['summary']['daily_count']}, "
          f"Weekly={report['summary']['weekly_count']}, "
          f"Monthly={report['summary']['monthly_count']}, "
          f"Disabled={report['summary']['disabled_count']}")
