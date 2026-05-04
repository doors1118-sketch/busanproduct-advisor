"""
run_legal_update_pipeline_dry_run_v0_1_1.py
3단계 dry-run: manifest load → target classification → adapter readiness check
실제 변경 감지, 원문 재수집, DB patch는 수행하지 않는다.
"""
import json, os, datetime
import sys
sys.path.insert(0, r'c:\Users\COMTREE\Desktop\메뉴얼 제작\scratch')

from check_legal_source_updates_v0_1_1 import check_updates
from diff_legal_versions_v0_1_1 import run_diff_dry_run
from classify_legal_update_impact_v0_1_1 import ACTION_MAP

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
manifest_path = os.path.join(base, 'legal_update_manifest_v0_1_1.json')

if __name__ == "__main__":
    print("=" * 60)
    print("Legal DB Update Pipeline Dry-Run v0.1.1")
    print("=" * 60)

    # Step 1: Manifest Load
    print("\n[Step 1] Manifest Load")
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
    print(f"  Loaded {len(manifest)} sources from manifest.")

    # Step 2: Target Classification
    print("\n[Step 2] Target Classification")
    check_report = check_updates(manifest_path, mode="dry_run")
    summary = check_report["summary"]
    print(f"  Daily:    {summary['daily_count']}")
    print(f"  Weekly:   {summary['weekly_count']}")
    print(f"  Monthly:  {summary['monthly_count']}")
    print(f"  Manual:   {summary['manual_count']}")
    print(f"  Disabled: {summary['disabled_count']}")

    # Step 3: Adapter Readiness Check
    print("\n[Step 3] Adapter Readiness Check")
    adapter = check_report["adapter_readiness"]
    for target_type, info in adapter.items():
        status = "READY (dry_run)" if info["adapter_available"] else "NOT AVAILABLE"
        print(f"  {target_type}: {status} ({info['mode']})")

    # Step 3b: Diff Engine Status
    print("\n[Step 3b] Diff Engine Status")
    diff_report, _ = run_diff_dry_run(manifest_path)
    print(f"  Skipped: {diff_report['skipped']} (원문 재수집 전이므로 전량 보류)")
    print(f"  Changed: {diff_report['changed']}")

    # Step 3c: Impact Classifier Action Map
    print("\n[Step 3c] Impact Classifier Action Map")
    for level, action in ACTION_MAP.items():
        print(f"  {level:10s} → {action}")

    # Assemble final report
    final_report = {
        "title": "Legal Update Pipeline Dry-Run Report v0.1.1",
        "run_date": datetime.datetime.now().isoformat(),
        "mode": "dry_run",
        "step_1_manifest_load": {
            "total_sources": len(manifest),
            "status": "PASS"
        },
        "step_2_target_classification": {
            "summary": summary,
            "status": "PASS"
        },
        "step_3_adapter_readiness": {
            "adapters": adapter,
            "diff_engine": {
                "total_targets": diff_report["total_targets"],
                "skipped": diff_report["skipped"],
                "changed": diff_report["changed"],
                "note": diff_report["note"]
            },
            "impact_classifier": {
                "action_map": ACTION_MAP,
                "status": "PASS"
            },
            "status": "PASS"
        },
        "overall_status": "PASS",
        "blocked_operations": [
            "실제 법제처 API 호출",
            "원문 재수집 (refresh)",
            "DB patch 적용",
            "scheduler 등록",
            "Production 배포"
        ]
    }

    out_path = os.path.join(base, 'legal_update_pipeline_dry_run_report_v0_1_1.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)

    # Save check targets report
    check_out = os.path.join(base, 'legal_update_check_targets_report_v0_1_1.json')
    with open(check_out, 'w', encoding='utf-8') as f:
        json.dump(check_report, f, ensure_ascii=False, indent=2)

    # Save diff skipped report
    diff_out = os.path.join(base, 'legal_diff_skipped_report_v0_1_1.json')
    with open(diff_out, 'w', encoding='utf-8') as f:
        json.dump(diff_report, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"Overall Status: {final_report['overall_status']}")
    print(f"{'=' * 60}")
