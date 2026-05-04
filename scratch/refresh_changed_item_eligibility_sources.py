"""
refresh_changed_item_eligibility_sources.py
변경이 감지된 Item Eligibility 소스만 선택적으로 재수집하는 dry-run 스크립트.
현재 단계에서는 실제 재수집 없이 대상 목록만 생성한다.
"""
import json, os, datetime

def refresh_sources(changed_list):
    results = []
    for item in changed_list:
        results.append({
            "source_name": item.get("source_name"),
            "refresh_status": "skipped_dry_run",
            "reason": "실제 재수집 파이프라인 미구축 상태"
        })
    return results

if __name__ == "__main__":
    print("Refresh: dry_run mode. No actual refresh performed.")
