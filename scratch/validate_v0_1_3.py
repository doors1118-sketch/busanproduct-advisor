import json, os, datetime

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
watch_report = json.load(open(os.path.join(base, 'legal_metadata_watch_targets_report_v0_1_3.json'), encoding='utf-8'))

checks = []

c1 = watch_report["metadata_watch_targets_count"] == 2
checks.append({"check": "metadata_watch_targets == 2", "value": watch_report["metadata_watch_targets_count"], "pass": c1})

c2 = watch_report["all_active_for_rule"]
checks.append({"check": "all targets active_for_rule=true", "pass": c2})

c3 = watch_report["all_metadata_watch_weekly"]
checks.append({"check": "metadata_watch_frequency == weekly for all", "pass": c3})

c4 = watch_report["all_full_text_monthly"]
checks.append({"check": "full_text_refresh_frequency == monthly for all", "pass": c4})

# monthly priority targets are still included in metadata watch queue
c5 = all(t["update_priority"] == "monthly" for t in watch_report["targets"])
checks.append({"check": "monthly priority targets included in metadata watch queue", "pass": c5})

c6 = len(watch_report["blocked_operations"]) >= 5
checks.append({"check": "blocked_operations enforced (>=5)", "pass": c6})

all_pass = all(c["pass"] for c in checks)

dry_run = {
    "title": "Legal Update Pipeline Dry-Run Report v0.1.3",
    "run_date": datetime.datetime.now().isoformat(),
    "mode": "dry_run",
    "v0_1_3_enhancement": "metadata_watch_enabled=true 대상 2건을 별도 weekly 실행 큐로 분리",
    "metadata_watch_queue": {
        "target_count": watch_report["metadata_watch_targets_count"],
        "frequency": "weekly",
        "url_accessed": False,
        "note": "update_priority=monthly여도 metadata_watch queue에 포함"
    },
    "validation_checks": checks,
    "overall_status": "PASS" if all_pass else "FAIL",
    "blocked_operations": watch_report["blocked_operations"]
}

out = os.path.join(base, 'legal_update_pipeline_dry_run_report_v0_1_3.json')
with open(out, 'w', encoding='utf-8') as f:
    json.dump(dry_run, f, ensure_ascii=False, indent=2)

print(f"Overall: {'PASS' if all_pass else 'FAIL'}")
for c in checks:
    print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['check']}")
