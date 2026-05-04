"""
import_direct_production_requirements.py
직접생산확인 기준 목록을 import하는 dry-run 스크립트.
"""
import json, os, datetime, hashlib, uuid

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

def generate_id(): return str(uuid.uuid4())[:8]
def hash_record(r): return hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]

def import_requirements(input_data):
    results = {"new": [], "updated": [], "needs_review": []}

    for item in input_data:
        code = item.get("detail_item_code")
        if not code:
            item["review_status"] = "needs_review"
            item["reason"] = "detail_item_code_missing"
            results["needs_review"].append(item)
            continue

        item["requirement_id"] = f"req_{generate_id()}"
        item["version_hash"] = hash_record(item)
        item["review_status"] = "verified"
        results["new"].append(item)

    return results

mock_input = [
    {"detail_item_code": "4617162201", "detail_item_name": "영상감시장치", "direct_production_required": True, "required_facility_summary": "조립 공정 및 검사 설비 보유 필수", "required_process_summary": "PCB 조립, 렌즈 조립, 기능검사", "standard_article_ref": "제3조", "effective_from": "2024-01-01", "effective_to": "2026-12-31"},
    {"detail_item_code": "4016020801", "detail_item_name": "데스크톱컴퓨터", "direct_production_required": True, "required_facility_summary": "조립라인, 검사장비 보유", "required_process_summary": "본체 조립, OS 설치, 기능검사", "standard_article_ref": "제4조", "effective_from": "2024-01-01", "effective_to": "2026-12-31"},
]

if __name__ == "__main__":
    results = import_requirements(mock_input)
    report = {
        "title": "Direct Production Requirement Import Report",
        "import_date": datetime.datetime.now().isoformat(),
        "mode": "dry_run",
        "summary": {k: len(v) for k, v in results.items()},
        "details": results
    }
    with open(os.path.join(base, 'direct_production_requirement_import_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Import dry-run: new={len(results['new'])}, needs_review={len(results['needs_review'])}")
