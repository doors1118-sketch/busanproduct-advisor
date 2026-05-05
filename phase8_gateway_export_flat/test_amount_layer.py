"""
Amount Layer 테스트 스크립트

금액 분기 로직의 핵심 동작을 검증한다.
pytest 없이 단독 실행 가능.
"""
import json
import sys
import os
from pathlib import Path

# 경로 설정
BASE_DIR = Path(r"c:\Users\COMTREE\Desktop\메뉴얼 제작")
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "phase8_gateway_export_flat"))

from amount_layer import resolve_active_rules, classify_amount, _to_int_or_none

# source_map 로드 (테스트용)
SMAP_PATH = BASE_DIR / "purchase_support_rule_source_map.json"
with open(SMAP_PATH, "r", encoding="utf-8") as f:
    TEST_SOURCE_MAP = json.load(f)

OUT_PATH_SCRATCH = BASE_DIR / "scratch" / "amount_layer_test_result.txt"
OUT_PATH_FLAT = BASE_DIR / "phase8_gateway_export_flat" / "amount_layer_test_result.txt"
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


# ── TC1: 물품 + 금액 미입력 → 소액수의 양쪽 + amount missing ──
lines.append("\n--- TC1: goods, amount=None, local ---")
result = resolve_active_rules(
    {"contract_object": "goods", "contract_method": "direct_contract"},
    TEST_SOURCE_MAP
)
check("R_DIRECT_GENERAL_SMALL_AMOUNT active",
      "R_DIRECT_GENERAL_SMALL_AMOUNT" in result["active_rule_ids"])
check("R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY active",
      "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY" in result["active_rule_ids"])
check("amount_classification = not_provided",
      result["amount_classification"] == "not_provided")
check("amount in missing_slots",
      "amount" in result["missing_slots"])
check("R_REGIONAL_RESTRICTION_GOODS active",
      "R_REGIONAL_RESTRICTION_GOODS" in result["active_rule_ids"])

# ── TC2: 물품 + 금액 20000000 (resolved_value=20M이므로 below_threshold) ──
lines.append("\n--- TC2: goods, amount=20000000, local (numeric resolved) ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 20000000, "contract_method": "direct_contract"},
    TEST_SOURCE_MAP
)
check("amount_classification = below_threshold",
      result["amount_classification"] == "below_threshold",
      f"actual: {result['amount_classification']}")
check("Only R_DIRECT_GENERAL_SMALL_AMOUNT active",
      "R_DIRECT_GENERAL_SMALL_AMOUNT" in result["active_rule_ids"]
      and "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY" not in result["active_rule_ids"])

# ── TC3: 물품 + 금액 200000000 (resolved_value=20M이므로 above_threshold) ──
lines.append("\n--- TC3: goods, amount=200000000, local (numeric resolved) ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 200000000, "contract_method": "direct_contract"},
    TEST_SOURCE_MAP
)
check("amount_classification = above_threshold",
      result["amount_classification"] == "above_threshold")

# ── TC4: 공사 + 지방계약 → 공동도급 활성 ──
lines.append("\n--- TC4: construction, law_system=local ---")
result = resolve_active_rules(
    {"contract_object": "construction", "law_system": "local"},
    TEST_SOURCE_MAP
)
check("R_LOCAL_REGIONAL_JOINT_CONTRACT active",
      "R_LOCAL_REGIONAL_JOINT_CONTRACT" in result["active_rule_ids"])
check("R_REGIONAL_RESTRICTION_CONSTRUCTION active",
      "R_REGIONAL_RESTRICTION_CONSTRUCTION" in result["active_rule_ids"])
check("R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK active",
      "R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK" in result["active_rule_ids"])

# ── TC5: MAS 경로 → MAS 규칙 활성 ──
lines.append("\n--- TC5: goods, procurement_route=mas ---")
result = resolve_active_rules(
    {"contract_object": "goods", "procurement_route": "mas"},
    TEST_SOURCE_MAP
)
check("R_SHOPPING_MALL_ROUTE_CLASSIFICATION active",
      "R_SHOPPING_MALL_ROUTE_CLASSIFICATION" in result["active_rule_ids"])
check("R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW active",
      "R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW" in result["active_rule_ids"])
# product_type 미입력이면 모든 threshold 규칙 활성화
check("All MAS threshold rules active (product_type=None)",
      "R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT" in result["active_rule_ids"]
      and "R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION" in result["active_rule_ids"]
      and "R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL" in result["active_rule_ids"])

# ── TC6: 제3자단가계약 ──
lines.append("\n--- TC6: third_party_unit_price_contract ---")
result = resolve_active_rules(
    {"contract_object": "goods", "procurement_route": "third_party_unit_price_contract"},
    TEST_SOURCE_MAP
)
check("R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW active",
      "R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW" in result["active_rule_ids"])

# ── TC7: 금지 표현 검사 ──
lines.append("\n--- TC7: forbidden phrases not in output ---")
forbidden = ["가능합니다", "구매 가능", "수의계약 가능", "지역제한 가능", "낙찰 가능"]
result_str = str(result)
for phrase in forbidden:
    check(f"'{phrase}' not in result", phrase not in result_str)

# ── TC8: classify_amount 단위 테스트 ──
lines.append("\n--- TC8: classify_amount unit tests ---")
check("None amount → not_provided", classify_amount(None, 50000000) == "not_provided")
check("None threshold → unresolved", classify_amount(20000000, None) == "unresolved")
check("20M < 50M → below_threshold", classify_amount(20000000, 50000000) == "below_threshold")
check("50M <= 50M → below_threshold", classify_amount(50000000, 50000000) == "below_threshold")
check("60M > 50M → above_threshold", classify_amount(60000000, 50000000) == "above_threshold")

# ── TC9: law_system 기본값 (부산시 = local) ──
lines.append("\n--- TC9: law_system default = local ---")
result = resolve_active_rules(
    {"contract_object": "construction"},
    TEST_SOURCE_MAP
)
check("Default local: R_LOCAL_REGIONAL_JOINT_CONTRACT active",
      "R_LOCAL_REGIONAL_JOINT_CONTRACT" in result["active_rule_ids"])

# ── TC10: 중복 제거 ──
lines.append("\n--- TC10: no duplicate rule_ids ---")
result = resolve_active_rules(
    {"contract_object": "goods", "contract_method": "direct_contract", "procurement_route": "mas"},
    TEST_SOURCE_MAP
)
check("No duplicates in active_rule_ids",
      len(result["active_rule_ids"]) == len(set(result["active_rule_ids"])))

# ── TC11: 용역 + 국가계약 ──
lines.append("\n--- TC11: service, law_system=national ---")
result = resolve_active_rules(
    {"contract_object": "service", "law_system": "national"},
    TEST_SOURCE_MAP
)
check("R_NATIONAL_REGIONAL_JOINT_CONTRACT active",
      "R_NATIONAL_REGIONAL_JOINT_CONTRACT" in result["active_rule_ids"])
check("R_REGIONAL_RESTRICTION_SERVICE active",
      "R_REGIONAL_RESTRICTION_SERVICE" in result["active_rule_ids"])

# ── TC12: amount 타입 정규화 (_to_int_or_none) ──
lines.append("\n--- TC12: amount type normalization ---")
check("int passthrough", _to_int_or_none(50000000) == 50000000)
check("string '50000000'", _to_int_or_none("50000000") == 50000000)
check("comma '100,000,000'", _to_int_or_none("100,000,000") == 100000000)
check("None → None", _to_int_or_none(None) is None)
check("invalid 'abc' → None", _to_int_or_none("abc") is None)
check("float 50000000.0 → 50000000", _to_int_or_none(50000000.0) == 50000000)

# ── TC13: 문자열 amount로 resolve_active_rules 호출 ──
lines.append("\n--- TC13: string amount in resolve_active_rules ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": "20,000,000", "contract_method": "direct_contract"},
    TEST_SOURCE_MAP
)
check("String amount '20,000,000' works without error and resolves",
      result["amount_classification"] == "below_threshold")

# ── TC14: 후보업체 조회 규칙 활성화 ──
lines.append("\n--- TC14: candidate lookup rules ---")
result = resolve_active_rules(
    {"contract_object": "goods"},
    TEST_SOURCE_MAP
)
check("R_COMPANY_CANDIDATE_LOOKUP_GOODS active for goods",
      "R_COMPANY_CANDIDATE_LOOKUP_GOODS" in result["active_rule_ids"])

result = resolve_active_rules(
    {"contract_object": "service"},
    TEST_SOURCE_MAP
)
check("R_COMPANY_CANDIDATE_LOOKUP_SERVICE active for service",
      "R_COMPANY_CANDIDATE_LOOKUP_SERVICE" in result["active_rule_ids"])

result = resolve_active_rules(
    {"contract_object": "construction"},
    TEST_SOURCE_MAP
)
check("R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION active for construction",
      "R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION" in result["active_rule_ids"])

# ── TC15: parameter_ref 일치 검증 ──
lines.append("\n--- TC15: parameter_ref consistency ---")
entry = TEST_SOURCE_MAP.get("R_DIRECT_GENERAL_SMALL_AMOUNT", {})
actual_refs = [p.get("parameter_ref") for p in entry.get("numeric_parameters", [])]
check("Source map has P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD",
      "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD" in actual_refs,
      f"actual refs: {actual_refs}")
# amount_layer.py에서 참조하는 ref가 source map과 일치하는지 간접 검증
# 만약 불일치하면 _get_resolved_threshold가 None을 반환 → unresolved
# resolved_value를 임시로 넣어서 매칭 확인
import copy
test_map = copy.deepcopy(TEST_SOURCE_MAP)
for p in test_map["R_DIRECT_GENERAL_SMALL_AMOUNT"]["numeric_parameters"]:
    if p["parameter_ref"] == "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD":
        p["resolved_value"] = 50000000
        p["requires_manual_numeric_verification"] = False
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 20000000, "contract_method": "direct_contract"},
    test_map
)
check("With resolved_value=50M, amount=20M → below_threshold",
      result["amount_classification"] == "below_threshold",
      f"actual: {result['amount_classification']}")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 60000000, "contract_method": "direct_contract"},
    test_map
)
check("With resolved_value=50M, amount=60M → above_threshold",
      result["amount_classification"] == "above_threshold",
      f"actual: {result['amount_classification']}")

# ── TC16: competitive_bid에서 수의계약 비활성화 ──
lines.append("\n--- TC16: competitive_bid does not activate direct contract ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 200000000, "contract_method": "competitive_bid"},
    TEST_SOURCE_MAP
)
check("R_DIRECT_GENERAL_SMALL_AMOUNT NOT active for competitive_bid",
      "R_DIRECT_GENERAL_SMALL_AMOUNT" not in result["active_rule_ids"])
check("R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY NOT active for competitive_bid",
      "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY" not in result["active_rule_ids"])
check("R_DIRECT_POLICY_COMPANY NOT active for competitive_bid",
      "R_DIRECT_POLICY_COMPANY" not in result["active_rule_ids"])

# ── TC17: contract_method=None + amount → 수의계약 활성화 (해당하는 것만) ──
lines.append("\n--- TC17: contract_method=None + amount → single direct rule ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 30000000},
    TEST_SOURCE_MAP
)
check("contract_method=None+amount: R_DIRECT_GENERAL_SMALL_AMOUNT inactive",
      "R_DIRECT_GENERAL_SMALL_AMOUNT" not in result["active_rule_ids"])
check("contract_method=None+amount: R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY active",
      "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY" in result["active_rule_ids"])

# ── TC18: 일반 기업 + 3천만원 + 2인 견적 → 불가 (20M 초과) ──
lines.append("\n--- TC18: General, 30M, 2-quote ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 30000000, "company_type": "general", "quote_type": "2_quote"},
    TEST_SOURCE_MAP
)
check("General 30M is above_threshold", result["amount_classification"] == "above_threshold")

# ── TC19: 여성 기업 + 40M + 1인 견적 → 가능 (50M 이하) ──
lines.append("\n--- TC19: Women, 40M, 1-quote ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 40000000, "company_type": "women", "quote_type": "1_quote"},
    TEST_SOURCE_MAP
)
check("Women 40M 1-quote is below_threshold", result["amount_classification"] == "below_threshold")
check("threshold_ref_used is P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD", 
      result["threshold_ref_used"] == "P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD",
      f"actual: {result['threshold_ref_used']}")
check("threshold_value_used is 50000000", result["threshold_value_used"] == 50000000)

# ── TC20: 소기업 + 80M + 2인 견적 → 가능 (100M 이하) ──
lines.append("\n--- TC20: Small business, 80M, 2-quote ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 80000000, "company_type": "small_business", "quote_type": "2_quote"},
    TEST_SOURCE_MAP
)
check("Small business 80M 2-quote is below_threshold", result["amount_classification"] == "below_threshold")

# ── TC21: 여성 기업 + 120M + 2인 견적 → 불가 (100M 초과) ──
lines.append("\n--- TC21: Women, 120M, 2-quote ---")
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 120000000, "company_type": "women", "quote_type": "2_quote"},
    TEST_SOURCE_MAP
)
check("Women 120M 2-quote is above_threshold", result["amount_classification"] == "above_threshold")

# ── TC22: parameter_status == 'candidate_only' 시 unresolved 처리 검증 ──
lines.append("\n--- TC22: parameter_status candidate_only -> unresolved ---")
test_map2 = copy.deepcopy(TEST_SOURCE_MAP)
for p in test_map2["R_DIRECT_GENERAL_SMALL_AMOUNT"]["numeric_parameters"]:
    if p["parameter_ref"] == "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD":
        p["resolved_value"] = 20000000
        p["parameter_status"] = "candidate_only"
        p["requires_manual_numeric_verification"] = True
result = resolve_active_rules(
    {"contract_object": "goods", "amount": 20000000, "contract_method": "direct_contract"},
    test_map2
)
check("candidate_only resolves to unresolved", result["amount_classification"] == "unresolved")

# ── TC23: source_map 인자 없이 resolve_active_rules() 호출 (자동 로드 검증) ──
lines.append("\n--- TC23: Auto-load source_map (source_map=None) ---")
result_auto = resolve_active_rules(
    {"contract_object": "goods", "amount": 20000000, "contract_method": "direct_contract"}
    # source_map 생략
)
check("amount_classification is below_threshold (not unresolved)", result_auto["amount_classification"] == "below_threshold")
check("threshold_value_used is 20M", result_auto["threshold_value_used"] == 20000000)

# ── TC24: review_all_routes=True 테스트 ──
lines.append("\n--- TC24: review_all_routes=True with competitive_bid ---")
result_all = resolve_active_rules(
    {"contract_object": "goods", "amount": 20000000, "contract_method": "competitive_bid", "review_all_routes": True},
    TEST_SOURCE_MAP
)
check("review_all_routes=True activates direct contract despite competitive_bid", 
      "R_DIRECT_GENERAL_SMALL_AMOUNT" in result_all["active_rule_ids"] or "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY" in result_all["active_rule_ids"])

# ──────────────────────────────────────────────────────────
# 결과 출력
# ──────────────────────────────────────────────────────────
lines.append("\n" + "=" * 60)
lines.append(f"RESULT: {passed} PASSED / {failed} FAILED")
lines.append("=" * 60)

result_text = "\n".join(lines)
with open(OUT_PATH_SCRATCH, "w", encoding="utf-8") as f:
    f.write(result_text)
with open(OUT_PATH_FLAT, "w", encoding="utf-8") as f:
    f.write(result_text)

print(f"[AMOUNT LAYER TEST] {passed} PASSED / {failed} FAILED")
print(f"[SAVED] {OUT_PATH_FLAT}")
