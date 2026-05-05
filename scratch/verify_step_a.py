"""
Step A 검증: production 승격된 source_map.json이 v2 데이터와 일치하는지 확인
+ Evidence Context Loader 호환성 검증
"""
import json
from pathlib import Path

BASE = Path(r"c:\Users\COMTREE\Desktop\메뉴얼 제작")
PROD_PATH = BASE / "purchase_support_rule_source_map.json"
V2_PATH = BASE / "purchase_support_rule_source_map.merged.v2.json"
BACKUP_PATH = BASE / "purchase_support_rule_source_map.backup.json"

lines = []
passed = 0
failed = 0

def check(label, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        lines.append(f"  [PASS] {label}")
    else:
        failed += 1
        lines.append(f"  [FAIL] {label}")
    if detail:
        lines.append(f"         {detail}")

lines.append("=" * 60)
lines.append("Step A Verification: Production Promotion")
lines.append("=" * 60)

# 1. 파일 존재
lines.append("\n--- 1. File existence ---")
check("production source_map.json exists", PROD_PATH.exists())
check("backup.json exists", BACKUP_PATH.exists())
check("v2.json still exists", V2_PATH.exists())

# 2. 내용 일치
lines.append("\n--- 2. Content match ---")
with open(PROD_PATH, "r", encoding="utf-8") as f:
    prod = json.load(f)
with open(V2_PATH, "r", encoding="utf-8") as f:
    v2 = json.load(f)
check("Production == v2 (identical content)", prod == v2)
check("Rule count = 37", len(prod) == 37)

# 3. v2 특징 보존
lines.append("\n--- 3. v2 features preserved ---")

# mapped_verified 엄격성
for rule_id, entry in prod.items():
    if entry["source_chain_status"] == "mapped_verified":
        for d in entry.get("primary_source_details", []):
            if d.get("status") == "candidate_needs_review":
                check(f"[{rule_id}] no candidate in mapped_verified", False)
                break
        else:
            check(f"[{rule_id}] mapped_verified is strict", True)

# pending_resolution = 0
pending = [k for k,v in prod.items() if v["source_chain_status"] == "pending_resolution"]
check("No pending_resolution rules", len(pending) == 0, f"pending={pending}")

# related_source_details populated
for rule_id, entry in prod.items():
    if len(entry.get("related_source_ids", [])) > 0:
        if len(entry.get("related_source_details", [])) == 0:
            check(f"[{rule_id}] related_source_details populated", False)
            break
else:
    check("All related_source_details populated", True)

# remaining_gap_reason consistency
for rule_id, entry in prod.items():
    has_unresolved = any(
        p.get("resolved_value") is None and p.get("requires_manual_numeric_verification")
        for p in entry.get("numeric_parameters", [])
    )
    if has_unresolved and entry.get("remaining_gap_reason") == "None":
        check(f"[{rule_id}] gap_reason not None when numeric unresolved", False)
        break
else:
    check("gap_reason consistency maintained", True)

# 4. Evidence Context Loader 호환성
lines.append("\n--- 4. Evidence Context Loader compatibility ---")
required_fields = ["rule_id", "display_name", "category", "primary_source_ids",
                    "related_source_ids", "source_chain_status", "primary_source_details",
                    "related_source_details", "numeric_parameters", "unmatched_query_terms"]
missing_fields = []
for rule_id, entry in prod.items():
    for field in required_fields:
        if field not in entry:
            missing_fields.append(f"{rule_id}.{field}")
check("All required fields present", len(missing_fields) == 0,
      f"missing: {missing_fields[:5]}" if missing_fields else "")

# 5. Backup integrity
lines.append("\n--- 5. Backup integrity ---")
with open(BACKUP_PATH, "r", encoding="utf-8") as f:
    backup = json.load(f)
check("Backup has 37 rules", len(backup) == 37)
check("Backup != production (v2 changes applied)", backup != prod)

lines.append("\n" + "=" * 60)
lines.append(f"RESULT: {passed} PASSED / {failed} FAILED")
lines.append("=" * 60)

result = "\n".join(lines)
out = BASE / "scratch" / "step_a_verify.txt"
with open(out, "w", encoding="utf-8") as f:
    f.write(result)
print(f"[STEP A] {passed} PASSED / {failed} FAILED")
print(f"[SAVED] {out}")
