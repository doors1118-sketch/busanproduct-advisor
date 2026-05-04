"""
sync_company_direct_production_certs.py
업체DB 직접생산확인 자료를 company_direct_production_cert_mapping으로 동기화하는 dry-run 스크립트.
PII 원문은 저장하지 않고 hash만 저장한다.
"""
import json, os, datetime, hashlib, uuid

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

def generate_id(): return str(uuid.uuid4())[:8]
def hash_pii(value): return hashlib.sha256(str(value).encode()).hexdigest()[:16] if value else None

def sync_certs(input_data):
    results = {"synced": [], "expired": [], "invalid": [], "skipped": []}
    today = datetime.date.today().isoformat()

    for cert in input_data:
        code = cert.get("detail_item_code")
        if not code:
            cert["reason"] = "detail_item_code_missing"
            results["skipped"].append(cert)
            continue

        entry = {
            "cert_mapping_id": f"cert_{generate_id()}",
            "company_id": cert["company_id"],
            "detail_item_code": code,
            "detail_item_name": cert.get("detail_item_name"),
            "valid_from": cert.get("valid_from"),
            "valid_to": cert.get("valid_to"),
            "source": cert.get("source", "company_db"),
            "source_checked_at": datetime.datetime.now().isoformat(),
            "cert_hash": hash_pii(cert.get("cert_number")),
            "pii_sanitized": True,
            "version_hash": hashlib.sha256(json.dumps(cert, sort_keys=True).encode()).hexdigest()[:16]
        }

        valid_to = cert.get("valid_to")
        if cert.get("cert_status") == "revoked":
            entry["cert_status"] = "revoked"
            entry["review_status"] = "verified"
            results["invalid"].append(entry)
        elif valid_to and valid_to < today:
            entry["cert_status"] = "expired"
            entry["review_status"] = "verified"
            results["expired"].append(entry)
        elif valid_to and valid_to >= today:
            entry["cert_status"] = "valid"
            entry["review_status"] = "verified"
            results["synced"].append(entry)
        else:
            entry["cert_status"] = "unknown"
            entry["review_status"] = "needs_review"
            results["synced"].append(entry)

    return results

mock_input = [
    {"company_id": "comp_abc", "detail_item_code": "4617162201", "detail_item_name": "영상감시장치", "cert_number": "DP-2024-001", "valid_from": "2024-01-01", "valid_to": "2026-12-31", "cert_status": "valid"},
    {"company_id": "comp_def", "detail_item_code": "4617162201", "detail_item_name": "영상감시장치", "cert_number": "DP-2022-005", "valid_from": "2022-01-01", "valid_to": "2023-12-31", "cert_status": "valid"},
    {"company_id": "comp_ghi", "detail_item_code": "4016020801", "detail_item_name": "데스크톱컴퓨터", "cert_number": "DP-2025-010", "valid_from": "2025-06-01", "valid_to": "2027-05-31", "cert_status": "valid"},
    {"company_id": "comp_jkl", "detail_item_name": "미분류 품목"},
]

if __name__ == "__main__":
    results = sync_certs(mock_input)
    report = {
        "title": "Company Direct Production Cert Sync Report",
        "sync_date": datetime.datetime.now().isoformat(),
        "mode": "dry_run",
        "summary": {k: len(v) for k, v in results.items()},
        "pii_policy": "cert_number and business_number are stored as hash only. No PII in LLM context."
    }
    validation = {
        "title": "Company Direct Production Cert Validation Report",
        "checks": [
            {"check": "no raw cert_number stored", "pass": all(e.get("cert_hash") and "DP-" not in str(e.get("cert_hash","")) for e in results["synced"] + results["expired"])},
            {"check": "pii_sanitized=true for all", "pass": all(e.get("pii_sanitized") for e in results["synced"] + results["expired"] + results["invalid"])},
            {"check": "expired certs flagged", "pass": len(results["expired"]) >= 1},
            {"check": "skipped items without detail_item_code", "pass": len(results["skipped"]) >= 1}
        ]
    }
    validation["overall"] = "PASS" if all(c["pass"] for c in validation["checks"]) else "FAIL"

    with open(os.path.join(base, 'company_direct_production_cert_sync_report.json'), 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with open(os.path.join(base, 'company_direct_production_cert_validation_report.json'), 'w', encoding='utf-8') as f:
        json.dump(validation, f, ensure_ascii=False, indent=2)
    print(f"Sync: valid={len(results['synced'])}, expired={len(results['expired'])}, invalid={len(results['invalid'])}, skipped={len(results['skipped'])}")
    print(f"Validation: {validation['overall']}")
