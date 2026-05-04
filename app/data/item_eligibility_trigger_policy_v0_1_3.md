# Item Eligibility Trigger Policy v0.1.3

본 문서는 Rule Engine에서 Item Eligibility 레이어를 호출하는 **트리거 조건**을 정의합니다.
Item Eligibility는 `item_eligibility_required = true`일 때만 호출되는 **조건부 레이어**입니다.

## 1. 핵심 원칙

- 직접생산확인은 **전체 계약판단의 공통 게이트가 아닙니다**.
- 직접생산확인은 **중소기업자간 경쟁제품으로 특정되거나, 사용자가 직생/중기경쟁제품을 명시한 경우**에만 작동하는 조건부 레이어입니다.
- `item_eligibility_required = false`이면 Item Eligibility 레이어는 **완전 스킵**됩니다.

## 2. 트리거 조건 (OR 결합 — 하나라도 충족 시 발동)

| # | 조건 | 판정 기준 | 예시 |
|:-:|------|-----------|------|
| T1 | **사용자 질의에 직생/중기경쟁 키워드 포함** | `user_query`에 다음 키워드가 포함: `직생`, `직접생산`, `직접생산확인`, `중소기업자간 경쟁제품`, `중기경쟁`, `중기경쟁제품` | "CCTV 직생도 봐줘" |
| T2 | **세부품명번호가 명시적으로 제공됨** | `detail_item_code`가 사용자 입력 또는 이전 대화에서 확정됨 | "세부품명번호 4617162201" |
| T3 | **item_alias_map이 중기경쟁제품 후보로 해소됨** | `item_alias_map` 조회 결과, 매칭된 세부품명 후보 중 하나 이상이 `is_sme_competition_product = true` | CCTV → 영상감시장치(경쟁제품) |
| T4 | **후보 업체에 직접생산확인 데이터가 존재** | `company_direct_production_cert_mapping`에 해당 `company_id`의 인증 데이터가 1건 이상 존재 | 업체 A → cert_status: valid |
| T5 | **계약경로상 중기경쟁제품 검증이 필수** | `procurement_route` 또는 `contract_method` 판정 결과, 중소기업자간 경쟁입찰이 적용되는 경로 | 중기경쟁 지정품목 + 추정가격 기준 이상 |

## 3. 트리거 판정 흐름도

```
사용자 질문 입력
    │
    ▼
[키워드 스캔] user_query에 직생/중기경쟁 키워드 있는가?
    ├─ Yes ──→ item_eligibility_required = true
    │
    ▼ No
[세부품명 확인] detail_item_code가 제공되었는가?
    ├─ Yes ──→ item_eligibility_required = true
    │
    ▼ No
[Alias 해소] item_alias_map 조회 결과 중기경쟁제품 후보가 있는가?
    ├─ Yes ──→ item_eligibility_required = true
    │
    ▼ No
[업체 인증 데이터] company_direct_production_cert 데이터가 존재하는가?
    ├─ Yes ──→ item_eligibility_required = true
    │
    ▼ No
[계약경로 확인] 중기경쟁제품 검증 필수 경로인가?
    ├─ Yes ──→ item_eligibility_required = true
    │
    ▼ No
    item_eligibility_required = false
    → Item Eligibility 레이어 완전 스킵
    → ❶~❼ 레이어만으로 답변 조립
```

## 4. 트리거 키워드 목록

```json
{
  "trigger_keywords": [
    "직생",
    "직접생산",
    "직접생산확인",
    "중소기업자간 경쟁제품",
    "중기경쟁",
    "중기경쟁제품",
    "경쟁제품 직접생산",
    "직접생산 확인증"
  ]
}
```

## 5. 비트리거 사례 (item_eligibility_required = false)

| 질문 | 트리거 판정 | 이유 |
|------|:-----------:|------|
| "8천만원 물품 수의계약 가능한가?" | `false` | 직생/중기경쟁 키워드 없음, 세부품명 미제공, 일반 금액·계약방식 질문 |
| "부산업체 쓸 수 있는 방법 알려줘" | `false` | 지역제한·정책기업 질문, 품목 특정 없음 |
| "3억 공사 지역제한 가능?" | `false` | 공사 질문, 물품 중기경쟁과 무관 |
| "사회적기업 수의계약 한도?" | `false` | 정책기업 특례 질문, 품목 무관 |

## 6. 트리거 사례 (item_eligibility_required = true)

| 질문 | 트리거 판정 | 해당 조건 |
|------|:-----------:|-----------|
| "CCTV 부산업체 찾아줘. 직생도 봐줘." | `true` | T1 (키워드 "직생") |
| "세부품명번호 4617162201 영상감시장치" | `true` | T2 (세부품명번호 명시) |
| "컴퓨터 살 건데 중기경쟁제품인지 확인해줘" | `true` | T1 (키워드 "중기경쟁제품") |
| "업체 A가 직접생산확인 있는지 봐줘" | `true` | T1 (키워드 "직접생산확인") + T4 (업체 인증 데이터) |

## 7. 기존 문서 대체 관계

- `item_eligibility_rule_integration_plan.md` → **superseded** (본 문서 + `rule_engine_priority_order_v0_1.md`로 대체)
- `item_eligibility_rule_integration_plan_v0_1_2.md` → **superseded** (본 문서 + `rule_engine_priority_order_v0_1.md`로 대체)
