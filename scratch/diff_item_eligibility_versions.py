"""
diff_item_eligibility_versions.py
Item Eligibility 데이터의 구/신 버전 간 diff를 수행하는 dry-run 스크립트.
version_hash 비교를 통해 변경 유형을 분류한다.
"""
import json

DIFF_TYPES = [
    "designation_added", "designation_removed", "designation_period_changed",
    "requirement_changed", "facility_changed", "process_changed",
    "cert_status_changed", "cert_expired", "cert_renewed", "metadata_only"
]

def diff_item_versions(old_hash, new_hash, source_name):
    if new_hash is None:
        return {"source_name": source_name, "diff_status": "skipped", "reason": "new_version_not_available"}
    if old_hash == new_hash:
        return {"source_name": source_name, "diff_status": "unchanged"}
    return {"source_name": source_name, "diff_status": "changed", "diff_types_available": DIFF_TYPES}

if __name__ == "__main__":
    result = diff_item_versions("hash_old", None, "sme_competition_product_list")
    print(json.dumps(result, ensure_ascii=False, indent=2))
