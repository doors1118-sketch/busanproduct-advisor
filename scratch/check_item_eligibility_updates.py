"""
check_item_eligibility_updates.py
Item Eligibility 데이터의 변경 여부를 확인하는 dry-run 스크립트.
실제 API 호출 없이 대상 분류만 수행한다.
"""
import json, os, datetime

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

def check_updates():
    manifest = json.load(open(os.path.join(base, 'item_eligibility_update_manifest.json'), encoding='utf-8'))
    report = {
        "title": "Item Eligibility Update Check Report",
        "check_date": datetime.datetime.now().isoformat(),
        "mode": "dry_run",
        "sources": []
    }
    for src in manifest["data_sources"]:
        report["sources"].append({
            "source_name": src["source_name"],
            "update_priority": src["update_priority"],
            "adapter_available": src["adapter_available"],
            "check_result": "skipped_dry_run",
            "note": "실제 API/파일 체크 미수행. 대상 분류만 완료."
        })
    return report

if __name__ == "__main__":
    report = check_updates()
    print(f"Checked {len(report['sources'])} sources (dry_run).")
