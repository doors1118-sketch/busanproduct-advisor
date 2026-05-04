"""
import_sme_competition_product_items.py
중소기업자간 경쟁제품 목록을 seed data로 import하는 dry-run 스크립트.
실제 DB 반영 없이 import_report를 생성한다.
"""
import json, os, datetime, hashlib, uuid

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

def generate_id(): return str(uuid.uuid4())[:8]
def hash_record(r): return hashlib.sha256(json.dumps(r, sort_keys=True).encode()).hexdigest()[:16]

def import_sme_products(input_data):
    results = {"new": [], "duplicate": [], "needs_review": [], "expired": []}
    existing_codes = set()

    for item in input_data:
        code = item.get("detail_item_code")
        if not code:
            item["review_status"] = "needs_review"
            item["reason"] = "detail_item_code_missing"
            results["needs_review"].append(item)
            continue

        if code in existing_codes:
            item["reason"] = "duplicate_in_batch"
            results["duplicate"].append(item)
            continue

        effective_to = item.get("effective_to")
        if effective_to and effective_to < datetime.date.today().isoformat():
            item["review_status"] = "expired"
            results["expired"].append(item)
        else:
            item["review_status"] = "verified"
            item["designation_id"] = f"desig_{generate_id()}"
            item["version_hash"] = hash_record(item)
            results["new"].append(item)

        existing_codes.add(code)

    return results

# Mock seed data
mock_input = [
    {"detail_item_code": "4617162201", "detail_item_name": "영상감시장치", "source_document_name": "중기경쟁제품 고시", "effective_from": "2024-01-01", "effective_to": "2026-12-31"},
    {"detail_item_code": "4617162202", "detail_item_name": "차량번호인식카메라", "source_document_name": "중기경쟁제품 고시", "effective_from": "2024-01-01", "effective_to": "2026-12-31"},
    {"detail_item_code": "4016020801", "detail_item_name": "데스크톱컴퓨터", "source_document_name": "중기경쟁제품 고시", "effective_from": "2024-01-01", "effective_to": "2026-12-31"},
    {"detail_item_name": "미분류 펌프", "source_document_name": "미확인"},
    {"detail_item_code": "4617162201", "detail_item_name": "영상감시장치(중복)", "source_document_name": "중기경쟁제품 고시", "effective_from": "2024-01-01", "effective_to": "2026-12-31"},
]

if __name__ == "__main__":
    results = import_sme_products(mock_input)
    report = {
        "title": "SME Competition Product Seed Import Report",
        "import_date": datetime.datetime.now().isoformat(),
        "mode": "dry_run",
        "summary": {k: len(v) for k, v in results.items()},
        "details": results
    }
    with open(os.path.join(base, 'item_eligibility_seed_import_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Import dry-run: new={len(results['new'])}, dup={len(results['duplicate'])}, needs_review={len(results['needs_review'])}, expired={len(results['expired'])}")
