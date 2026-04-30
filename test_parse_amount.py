"""parse_amount smoke test"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
os.chdir(os.path.join(os.path.dirname(__file__), 'app'))
from gemini_engine import _parse_amount, _detect_regional_preference, _build_amount_route_template

# ── parse_amount tests ──
tests = [
    ("7천만원으로 컴퓨터 구매", 70_000_000),
    ("7000만원 물품", 70_000_000),
    ("70,000,000원 짜리", 70_000_000),
    ("70000000원", 70_000_000),
    ("1억원 공사", 100_000_000),
    ("1억5천만원 물품", 150_000_000),
    ("2천만원 컴퓨터", 20_000_000),
    ("8천만원 물품 수의계약", 80_000_000),
    ("5백만원 소모품", 5_000_000),
    ("500만원 소모품", 5_000_000),
    ("혁신제품이면 금액 제한 없이", None),
]

print("=== _parse_amount smoke test ===")
passed = 0
for text, expected in tests:
    result = _parse_amount(text)
    ok = result == expected
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: \"{text}\" -> {result} (expected {expected})")
    if ok:
        passed += 1
print(f"\n  {passed}/{len(tests)} passed\n")

# ── detect_regional_preference tests ──
print("=== _detect_regional_preference smoke test ===")
regional_tests = [
    ("7천만원으로 컴퓨터 구매해야 한다. 가급적 지역업체랑 계약하고 싶은데", True),
    ("8천만원 물품 수의계약 가능해?", False),
    ("2천만원 컴퓨터 부산업체랑 계약하고 싶어", True),
    ("혁신제품이면 금액 제한 없이 수의계약 가능해?", False),
]
rp = 0
for text, expected in regional_tests:
    result = _detect_regional_preference(text)
    ok = result == expected
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: \"{text[:40]}...\" -> {result} (expected {expected})")
    if ok:
        rp += 1
print(f"\n  {rp}/{len(regional_tests)} passed\n")

# ── build_amount_route_template tests ──
print("=== _build_amount_route_template smoke test ===")

# Test A: 7천만원 + 지역업체
ans_a, meta_a = _build_amount_route_template(70_000_000, True)
checks_a = [
    ("일반 소액 수의계약 기준" in ans_a, "A.금액대 판단 포함"),
    ("정책기업 수의계약 기준(5천만원 이하) 모두 초과" in ans_a, "5천만 초과 표현"),
    ("지역제한 제한경쟁입찰" in ans_a, "지역제한 경쟁 경로"),
    ("지역업체 가점" in ans_a, "지역업체 가점 경로"),
    ("MAS(다수공급자계약)" in ans_a, "MAS 경로"),
    ("혁신제품·우수조달물품·기술개발제품" in ans_a, "혁신/기술 경로"),
    ("지역의무공동도급은 공사" in ans_a, "공동도급 주의문"),
    (meta_a["regional_route_guidance_provided"] == True, "meta: regional=True"),
    (meta_a["route_guidance_provided"] == True, "meta: route=True"),
    (meta_a["local_restricted_bid_route_check_required"] == True, "meta: local_restricted=True"),
]
bp = 0
for ok, label in checks_a:
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {label}")
    if ok:
        bp += 1

# Test B: 2천만원 + 지역업체 없음
ans_b, meta_b = _build_amount_route_template(20_000_000, False)
checks_b = [
    ("일반 소액 수의계약 기준(추정가격 2천만원 이하) 이내" in ans_b, "2천만 이내 표현"),
    ("나라장터 종합쇼핑몰" in ans_b, "비지역 경로 안내"),
    (meta_b["regional_route_guidance_provided"] == False, "meta: regional=False"),
]
for ok, label in checks_b:
    status = "PASS" if ok else "FAIL"
    print(f"  {status}: {label}")
    if ok:
        bp += 1

print(f"\n  {bp}/{len(checks_a) + len(checks_b)} passed\n")

total = passed + rp + bp
total_tests = len(tests) + len(regional_tests) + len(checks_a) + len(checks_b)
print(f"=== TOTAL: {total}/{total_tests} passed ===")
if total == total_tests:
    print("ALL SMOKE TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
