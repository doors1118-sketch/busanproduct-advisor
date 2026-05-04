"""
verify_watch_report.py
CI/자동 검증용 — assert 기반. 실패 시 sys.exit(1).
"""
import json, os, sys

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
report = json.load(open(os.path.join(base, 'legal_metadata_watch_targets_report_v0_1_3.json'), encoding='utf-8'))

failures = []

def check(name, condition):
    if condition:
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name}")
        failures.append(name)

# 1. metadata_watch_targets_count == 2
check("metadata_watch_targets_count == 2",
      report["metadata_watch_targets_count"] == 2)

# 2. all_active_for_rule == true
check("all_active_for_rule == true",
      report["all_active_for_rule"] is True)

# 3. all_metadata_watch_weekly == true
check("all_metadata_watch_weekly == true",
      report["all_metadata_watch_weekly"] is True)

# 4. all_full_text_monthly == true
check("all_full_text_monthly == true",
      report["all_full_text_monthly"] is True)

# 5. exact title set match
titles = set(t["normalized_title"] for t in report["targets"])
expected = {"지방자치단체 입찰 및 계약집행기준", "지방자치단체 입찰시 낙찰자 결정기준"}
check(f"exact title set match ({len(titles)} == {len(expected)})",
      titles == expected)

# 6. all update_priority == monthly
check("all update_priority == monthly",
      all(t["update_priority"] == "monthly" for t in report["targets"]))

# 7. all watch_status == pending_dry_run
check("all watch_status == pending_dry_run",
      all(t["watch_status"] == "pending_dry_run" for t in report["targets"]))

print()
if failures:
    print(f"FAILED ({len(failures)} checks)")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print(f"ALL PASS (7/7)")
    sys.exit(0)
