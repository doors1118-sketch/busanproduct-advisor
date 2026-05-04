"""
Generate v0.1.2 dry-run report and validate all outputs.
"""
import json, os, datetime

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

manifest = json.load(open(os.path.join(base, 'legal_update_manifest_v0_1_2.json'), encoding='utf-8'))
build_report = json.load(open(os.path.join(base, 'legal_update_manifest_build_report_v0_1_2.json'), encoding='utf-8'))
none_report = json.load(open(os.path.join(base, 'none_target_reason_report_v0_1_2.json'), encoding='utf-8'))

checks = []

# 1. Total = 217
c1 = build_report["total_sources"] == 217
checks.append({"check": "manifest_total_sources == 217", "value": build_report["total_sources"], "pass": c1})

# 2. PDF metadata watch = 2
pdf_watch = [m for m in manifest if m["metadata_watch_enabled"]]
c2 = len(pdf_watch) == 2
checks.append({"check": "metadata_watch_enabled == 2", "value": len(pdf_watch), "pass": c2})

# 3. PDF watch targets are active_for_rule=true
c3 = all(m["active_for_rule"] for m in pdf_watch)
checks.append({"check": "pdf_watch_targets are active_for_rule=true", "pass": c3})

# 4. PDF watch have metadata_watch_frequency=weekly
c4 = all(m["metadata_watch_frequency"] == "weekly" for m in pdf_watch)
checks.append({"check": "pdf_watch_frequency == weekly", "pass": c4})

# 5. PDF watch have full_text_refresh_frequency=monthly
c5 = all(m["full_text_refresh_frequency"] == "monthly" for m in pdf_watch)
checks.append({"check": "full_text_refresh_frequency == monthly", "pass": c5})

# 6. None targets = 5
c6 = none_report["total_none_targets"] == 5
checks.append({"check": "none_targets == 5", "value": none_report["total_none_targets"], "pass": c6})

# 7. All none targets have none_reason
c7 = all(item.get("none_reason") for item in none_report["items"])
checks.append({"check": "all none targets have none_reason", "pass": c7})

# 8. All none targets have recommended_update_action
c8 = all(item.get("recommended_update_action") for item in none_report["items"])
checks.append({"check": "all none targets have recommended_update_action", "pass": c8})

# 9. No mock_id
c9 = not any("mock" in m["source_id"] for m in manifest)
checks.append({"check": "no mock_id in manifest", "pass": c9})

# 10. law_api_target enum only
api_vals = set(m["law_api_target"] for m in manifest)
c10 = api_vals.issubset({"law", "admrul", "ordinance", "none"})
checks.append({"check": "law_api_target is enum", "values": list(api_vals), "pass": c10})

all_pass = all(c["pass"] for c in checks)

dry_run_report = {
    "title": "Legal Update Pipeline Dry-Run Report v0.1.2",
    "run_date": datetime.datetime.now().isoformat(),
    "mode": "dry_run",
    "v0_1_2_enhancements": {
        "pdf_metadata_watch_policy": "2건 지방계약 핵심 PDF에 weekly 메타데이터 감시 분리 적용",
        "none_target_reason_report": "5건 none 대상에 사유·권장조치 필드 추가",
        "source_refresh_method_field": "원문 refresh와 메타데이터 watch를 분리하는 필드 신설"
    },
    "validation_checks": checks,
    "overall_status": "PASS" if all_pass else "FAIL",
    "blocked_operations": [
        "실제 법제처 API 호출",
        "실제 원문 재수집",
        "DB patch 적용",
        "scheduler 등록",
        "Production 배포"
    ]
}

out_path = os.path.join(base, 'legal_update_pipeline_dry_run_report_v0_1_2.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(dry_run_report, f, ensure_ascii=False, indent=2)

print(f"Overall: {'PASS' if all_pass else 'FAIL'}")
for c in checks:
    status = "PASS" if c["pass"] else "FAIL"
    print(f"  [{status}] {c['check']}")
