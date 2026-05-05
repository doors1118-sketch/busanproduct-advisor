"""
verify_source_map_consistency.py
Source Map의 상태값 정합성을 검증하는 유틸리티 스크립트입니다.
"""

import json
import sys
from pathlib import Path

def check_consistency(source_map_path: Path):
    if not source_map_path.exists():
        print(f"[ERROR] Source map not found at {source_map_path}")
        sys.exit(1)

    with open(source_map_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    errors = []
    
    for rule_id, rule_data in data.items():
        status = rule_data.get("source_chain_status")
        unmatched = rule_data.get("unmatched_query_terms", [])
        
        # 1. mapped_verified 정합성 검사
        if status == "mapped_verified" and unmatched:
            errors.append(f"[{rule_id}] status is 'mapped_verified' but has unmatched terms: {unmatched}")
            
        # 2. parameter 정합성 검사
        for param in rule_data.get("numeric_parameters", []):
            p_ref = param.get("parameter_ref")
            p_status = param.get("parameter_status")
            p_val = param.get("resolved_value")
            p_manual = param.get("requires_manual_numeric_verification")
            
            # resolved_value가 존재할 때의 정합성
            if p_val is not None:
                if p_status != "resolved":
                    errors.append(f"[{rule_id} / {p_ref}] has resolved_value ({p_val}) but status is '{p_status}' (expected 'resolved')")
                if p_manual is True:
                    errors.append(f"[{rule_id} / {p_ref}] has resolved_value ({p_val}) but requires_manual_numeric_verification is True")
            
            # status가 resolved인데 값이 없을 때의 정합성
            if p_status == "resolved" and p_val is None:
                errors.append(f"[{rule_id} / {p_ref}] status is 'resolved' but resolved_value is None")

    if errors:
        print(f"[FAIL] Found {len(errors)} consistency errors in source map:")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)
    else:
        print("[PASS] Source map consistency check passed. No issues found.")

if __name__ == "__main__":
    target_path = Path(__file__).resolve().parent / "purchase_support_rule_source_map.json"
    check_consistency(target_path)
