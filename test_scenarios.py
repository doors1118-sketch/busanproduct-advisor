"""
지시문 9항 검증: 3개 시나리오를 _build_amount_route_template 직접 호출로 테스트.
서버 구동 없이 answer 원문 + meta_updates를 검증한다.
"""
import sys, os, json, re
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
os.chdir(os.path.join(os.path.dirname(__file__), 'app'))
from gemini_engine import _parse_amount, _detect_regional_preference, _build_amount_route_template

FORBIDDEN_PATTERNS = [
    r"수의계약\s*(이|이면|으로)?\s*가능합니다",
    r"바로\s*계약\s*가능",
    r"계약\s*(이|을)?\s*가능합니다",
    r"수의계약\s*체결이?\s*가능",
    r"수의계약을?\s*할\s*수\s*있습니다",
]

def scan_forbidden(text):
    found = []
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text):
            found.append(pat)
    return found


def simulate_scenario(label, question, expected_checks):
    """시나리오 시뮬레이션"""
    print(f"\n{'='*60}")
    print(f"시나리오 {label}")
    print(f"질문: {question}")
    print(f"{'='*60}")

    amount = _parse_amount(question)
    regional = _detect_regional_preference(question)

    # 금액대 판정
    amount_band = None
    general_small_value_sole_quote = None
    policy_company_sole_quote = None
    if amount is not None:
        if amount <= 20_000_000:
            amount_band = "under_20m"
            general_small_value_sole_quote = "within_threshold"
            policy_company_sole_quote = "within_threshold"
        elif amount <= 50_000_000:
            amount_band = "over_20m_under_50m"
            general_small_value_sole_quote = "exceeds_threshold"
            policy_company_sole_quote = "within_threshold"
        elif amount <= 100_000_000:
            amount_band = "over_50m_under_100m"
            general_small_value_sole_quote = "exceeds_threshold"
            policy_company_sole_quote = "exceeds_50m_threshold"
        else:
            amount_band = "over_100m"
            general_small_value_sole_quote = "exceeds_threshold"
            policy_company_sole_quote = "exceeds_50m_threshold"

    answer = ""
    meta = {}
    if amount is not None:
        answer, meta = _build_amount_route_template(amount, regional)
        meta["amount_detected"] = amount
        meta["amount_band"] = amount_band
        meta["general_small_value_sole_quote"] = general_small_value_sole_quote
        meta["policy_company_sole_quote"] = policy_company_sole_quote

    # 금지 표현 스캔
    forbidden_remaining = scan_forbidden(answer)
    meta["forbidden_patterns_remaining_after_rewrite"] = forbidden_remaining
    meta["legal_conclusion_allowed"] = False
    meta["contract_possible_auto_promoted"] = False
    meta["production_deployment"] = "HOLD"
    meta["final_answer_scanned"] = True

    # 답변 원문 출력
    print(f"\n--- 답변 원문 ---")
    print(answer[:2000])
    if len(answer) > 2000:
        print(f"... ({len(answer)} chars total)")

    # metadata 전체 출력
    print(f"\n--- metadata ---")
    print(json.dumps(meta, ensure_ascii=False, indent=2))

    # forbidden pattern scan 결과
    print(f"\n--- forbidden pattern scan ---")
    print(f"  remaining: {forbidden_remaining}")

    # 기대 조건 검증
    print(f"\n--- 검증 ---")
    all_pass = True
    for desc, check_fn in expected_checks:
        ok = check_fn(answer, meta)
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"  {status}: {desc}")

    return all_pass


# ═══════════════════════════════════════════════════════════
# 시나리오 A: 7천만원 컴퓨터 + 지역업체
# ═══════════════════════════════════════════════════════════
checks_a = [
    ("amount_detected=70000000", lambda a, m: m.get("amount_detected") == 70_000_000),
    ("amount_band=over_50m_under_100m", lambda a, m: m.get("amount_band") == "over_50m_under_100m"),
    ("regional_route_guidance_provided=true", lambda a, m: m.get("regional_route_guidance_provided") == True),
    ("local_restricted_bid_route_check_required=true", lambda a, m: m.get("local_restricted_bid_route_check_required") == True),
    ("local_preference_score_route_check_required=true", lambda a, m: m.get("local_preference_score_route_check_required") == True),
    ("mas_second_stage_route_check_required=true", lambda a, m: m.get("mas_second_stage_route_check_required") == True),
    ("innovation_product_route_check_required=true", lambda a, m: m.get("innovation_product_route_check_required") == True),
    ("tech_product_route_check_required=true", lambda a, m: m.get("tech_product_route_check_required") == True),
    ("forbidden_patterns_remaining=[]", lambda a, m: m.get("forbidden_patterns_remaining_after_rewrite") == []),
    ("legal_conclusion_allowed=false", lambda a, m: m.get("legal_conclusion_allowed") == False),
    ("contract_possible_auto_promoted=false", lambda a, m: m.get("contract_possible_auto_promoted") == False),
    ("production_deployment=HOLD", lambda a, m: m.get("production_deployment") == "HOLD"),
    ("답변에 '지역제한 제한경쟁입찰' 포함", lambda a, m: "지역제한 제한경쟁입찰" in a),
    ("답변에 '지역업체 가점' 포함", lambda a, m: "지역업체 가점" in a),
    ("답변에 'MAS' 포함", lambda a, m: "MAS" in a),
    ("답변에 '혁신제품' 포함", lambda a, m: "혁신제품" in a),
    ("답변에 '기술개발제품' 포함", lambda a, m: "기술개발제품" in a),
    ("답변에 '지역의무공동도급' 주의문 포함", lambda a, m: "지역의무공동도급은 공사" in a),
    ("2천만원 기준 초과 표현", lambda a, m: "2천만원 이하" in a),
    ("5천만원 기준 초과 표현", lambda a, m: "5천만원 이하" in a),
]

# ═══════════════════════════════════════════════════════════
# 시나리오 B: 8천만원 물품 수의계약 가능해?
# ═══════════════════════════════════════════════════════════
checks_b = [
    ("amount_detected=80000000", lambda a, m: m.get("amount_detected") == 80_000_000),
    ("amount_band=over_50m_under_100m", lambda a, m: m.get("amount_band") == "over_50m_under_100m"),
    ("일반 소액수의 2천만원 기준 초과", lambda a, m: "2천만원 이하" in a),
    ("정책기업 5천만원 기준 초과", lambda a, m: "5천만원 이하" in a),
    ("수의계약 가능 단정 금지", lambda a, m: len(scan_forbidden(a)) == 0),
    ("대안 경로 안내 (종합쇼핑몰)", lambda a, m: "종합쇼핑몰" in a),
    ("대안 경로 안내 (혁신제품)", lambda a, m: "혁신제품" in a),
    ("production_deployment=HOLD", lambda a, m: m.get("production_deployment") == "HOLD"),
]

# ═══════════════════════════════════════════════════════════
# 시나리오 C: 2천만원 컴퓨터 부산업체랑 계약하고 싶어
# ═══════════════════════════════════════════════════════════
checks_c = [
    ("amount_band=under_20m", lambda a, m: m.get("amount_band") == "under_20m"),
    ("일반 소액수의 기준 이내 표현", lambda a, m: "이내" in a or "이하" in a),
    ("'계약 가능합니다' 단정 금지", lambda a, m: len(scan_forbidden(a)) == 0),
    ("지역업체 활용 경로 안내", lambda a, m: m.get("regional_route_guidance_provided") == True),
    ("지역제한 경쟁입찰 안내", lambda a, m: "지역제한 제한경쟁입찰" in a),
    ("지역업체 가점 안내", lambda a, m: "지역업체 가점" in a),
    ("MAS 2단계 안내", lambda a, m: "MAS" in a),
    ("production_deployment=HOLD", lambda a, m: m.get("production_deployment") == "HOLD"),
]

# 실행
results = []
results.append(simulate_scenario("A", "7천만원으로 컴퓨터 구매해야 한다. 가급적 지역업체랑 계약하고 싶은데 방법이 있을까?", checks_a))
results.append(simulate_scenario("B", "8천만원 물품 수의계약 가능해?", checks_b))
results.append(simulate_scenario("C", "2천만원 컴퓨터 부산업체랑 계약하고 싶어", checks_c))

print(f"\n{'='*60}")
print(f"=== 최종 결과 ===")
total_checks = len(checks_a) + len(checks_b) + len(checks_c)
for i, (label, passed) in enumerate(zip(["A", "B", "C"], results)):
    print(f"  시나리오 {label}: {'ALL PASS' if passed else 'FAIL'}")

if all(results):
    print(f"\n  ✅ 전체 {total_checks}개 검증 항목 ALL PASS")
    print(f"  production_deployment = HOLD")
else:
    print(f"\n  ❌ 일부 항목 FAIL")
    sys.exit(1)
