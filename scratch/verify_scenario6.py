import re
import sys

with open("live_e2e_with_gemini_result.md", "r", encoding="utf-8") as f:
    content = f.read()

idx = content.find("Scenario 6")
if idx == -1:
    raise RuntimeError("Scenario 6 section not found")

s6 = content[idx:]

m = re.search(r"```markdown\n(.*?)\n```", s6, re.DOTALL)
if not m:
    raise RuntimeError("Scenario 6 markdown block not found")

md_block = m.group(1)

failures = []

def check(name, condition):
    print(f"  {name}: {'PASS' if condition else 'FAIL'}")
    if not condition:
        failures.append(name)

print("=== 검증 항목 1: 필수 섹션 존재 ===")
check("업체 조회 조건 확인 필요", "업체 조회 조건 확인 필요" in md_block)
check("수의계약 검토 시 확인할 금액대", "수의계약 검토 시 확인할 금액대" in md_block)
check("추가로 필요한 정보", "추가로 필요한 정보" in md_block)

print("\n=== 검증 항목 2: 조문 발췌 details 없음 ===")
check("details 태그 없음", "<details>" not in md_block)

print("\n=== 검증 항목 3: 금지 표현 없음 ===")
forbidden = ["계약 가능합니다", "구매 가능합니다", "수의계약 가능합니다", "지역제한 가능합니다", "낙찰 가능합니다"]
found = [p for p in forbidden if p in md_block]
check(f"금지 표현 없음: {found}", not found)

print("\n=== 검증 항목 4: Source Map resolved 금액 표시 여부 ===")
amounts = ["20,000,000원", "50,000,000원", "100,000,000원"]
for amount in amounts:
    print(f"  {amount}: {'표시됨' if amount in md_block else '미표시'}")

fallback_phrase = "금액 기준은 현재 Source Map에서 검증된 resolved parameter가 확인될 때만 표시합니다."
print("\n=== 검증 항목 5: resolved parameter fallback 여부 ===")
if fallback_phrase in md_block:
    print("  resolved parameter 없음: fallback 안내 표시")
else:
    print("  resolved parameter 있음: 금액 기준 표시 경로로 추정")

print("\n=== 검증 항목 6: bullets 렌더링 ===")
for token in ["기술개발제품", "중소기업자간 경쟁제품", "품목명", "추정가격", "업체유형", "견적방식"]:
    check(token, token in md_block)

print("\n=== 검증 항목 7: Functional Status ===")
check("Scenario Functional Status PASS", "Scenario Functional Status: `PASS`" in s6)

print("\n=== 최종 판정 ===")
if failures:
    print(f"FAIL: {failures}")
    sys.exit(1)

print("PASS")
sys.exit(0)
