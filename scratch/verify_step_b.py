"""
Step B 통합 검증: company_api_mapping_required 규칙의 전체 파이프라인 정합성

확인 항목:
1. Amount Layer가 4개 candidate_lookup 규칙을 올바르게 활성화하는지
2. Evidence Policy가 company_api_mapping_required → company_api_only로 분류하는지
3. source_map에서 4개 규칙의 상태가 일관된지
4. CompanyAPIAdapter mock이 정상 동작하는지
"""
import json
import sys
from pathlib import Path

BASE = Path(r"c:\Users\COMTREE\Desktop\메뉴얼 제작")
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "phase8_gateway_export_flat"))

from amount_layer import resolve_active_rules
from app.answer_builder.evidence_policy import classify_rule_display_level
from company_api_adapter import CompanyAPIAdapter, CompanyCandidateResult

SMAP_PATH = BASE / "purchase_support_rule_source_map.json"
with open(SMAP_PATH, "r", encoding="utf-8") as f:
    source_map = json.load(f)

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
lines.append("Step B Verification: Company API Mapping Integration")
lines.append("=" * 60)

# ── 1. Amount Layer 활성화 ──
lines.append("\n--- 1. Amount Layer activates candidate_lookup rules ---")
API_RULES = {
    "goods": "R_COMPANY_CANDIDATE_LOOKUP_GOODS",
    "service": "R_COMPANY_CANDIDATE_LOOKUP_SERVICE",
    "construction": "R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION",
}
for obj, rule_id in API_RULES.items():
    result = resolve_active_rules({"contract_object": obj}, source_map)
    check(f"[{obj}] {rule_id} in active_rule_ids",
          rule_id in result["active_rule_ids"])

# MAS local supplier
result = resolve_active_rules(
    {"contract_object": "goods", "procurement_route": "mas"}, source_map
)
check("R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP active for MAS",
      "R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP" in result["active_rule_ids"])

# ── 2. Evidence Policy 분류 ──
lines.append("\n--- 2. Evidence Policy: company_api_mapping_required → company_api_only ---")
api_rule_ids = [
    "R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP",
    "R_COMPANY_CANDIDATE_LOOKUP_GOODS",
    "R_COMPANY_CANDIDATE_LOOKUP_SERVICE",
    "R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION",
]
for rule_id in api_rule_ids:
    entry = source_map.get(rule_id, {})
    display_level = classify_rule_display_level(entry)
    check(f"[{rule_id}] display_level = company_api_only",
          display_level == "company_api_only",
          f"actual: {display_level}")

# ── 3. Source map 상태 일관성 ──
lines.append("\n--- 3. Source map consistency for API rules ---")
for rule_id in api_rule_ids:
    entry = source_map.get(rule_id, {})
    check(f"[{rule_id}] status = company_api_mapping_required",
          entry.get("source_chain_status") == "company_api_mapping_required")
    # API 규칙은 legal source가 필요 없음 (GOODS/SERVICE/CONSTRUCTION은 primary 없어야 맞음)
    if rule_id != "R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP":
        # 물품/용역/공사 후보는 API 전용
        check(f"[{rule_id}] no primary_source_ids (API only)",
              len(entry.get("primary_source_ids", [])) == 0)

# MAS는 조달사업법 관련 source가 있을 수 있음
mas_entry = source_map.get("R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP", {})
check("R_MAS has some source_ids (조달사업법 관련)",
      len(mas_entry.get("primary_source_ids", [])) > 0 or
      len(mas_entry.get("related_source_ids", [])) > 0)

# ── 4. CompanyAPIAdapter mock 동작 ──
lines.append("\n--- 4. CompanyAPIAdapter mock test ---")
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class MockSlots:
    item_name: Optional[str] = "사무용 가구"
    location: Optional[str] = "부산"
    candidate_lookup_requested: bool = True

@dataclass
class MockRouterResult:
    candidate_lookup_required: bool = True
    slots: MockSlots = field(default_factory=MockSlots)

adapter = CompanyAPIAdapter(use_mock=True)

# 정상 조회
mock_rr = MockRouterResult()
result = adapter.resolve(mock_rr)
check("Mock search returns success", result.status == "success")
check("Mock returns 2 candidates", len(result.candidates) == 2)
check("Mock candidates have masked names",
      all("***" in c.company_name_masked for c in result.candidates))
check("Mock candidates have '검토 후보' status",
      all(c.display_status == "검토 후보" for c in result.candidates))

# 조회 스킵 (candidate_lookup_required=False)
skip_rr = MockRouterResult(candidate_lookup_required=False)
result = adapter.resolve(skip_rr)
check("Skipped when not required", result.status == "skipped")

# item_name 없음
no_item_rr = MockRouterResult()
no_item_rr.slots = MockSlots(item_name=None)
result = adapter.resolve(no_item_rr)
check("Skipped when no item_name", result.status == "skipped")

# ── 5. 전체 규칙 카운트 교차 검증 ──
lines.append("\n--- 5. Cross-verification ---")
total_api = sum(1 for v in source_map.values()
                if v["source_chain_status"] == "company_api_mapping_required")
check("Total API rules = 4", total_api == 4)
total_verified = sum(1 for v in source_map.values()
                     if v["source_chain_status"] == "mapped_verified")
check("mapped_verified = 9", total_verified == 9)
total_rules = len(source_map)
check("Total rules = 37", total_rules == 37)

lines.append("\n" + "=" * 60)
lines.append(f"RESULT: {passed} PASSED / {failed} FAILED")
lines.append("=" * 60)

result_text = "\n".join(lines)
out = BASE / "scratch" / "step_b_verify.txt"
with open(out, "w", encoding="utf-8") as f:
    f.write(result_text)
print(f"[STEP B] {passed} PASSED / {failed} FAILED")
print(f"[SAVED] {out}")
