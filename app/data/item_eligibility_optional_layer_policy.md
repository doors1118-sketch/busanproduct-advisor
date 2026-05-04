# Item Eligibility Optional Layer Policy

본 문서는 Item Eligibility가 Rule Engine 내에서 **선택적(Optional) 레이어**로 동작하는 원칙을 정의합니다.

## 1. 레이어 위치

Item Eligibility는 Rule Engine 8단계 중 **마지막 단계(❽)**에 위치합니다.
❶ buyer_type → ❷ contract_object → ❸ amount → ❹ procurement_route → ❺ contract_method → ❻ local_preference → ❼ policy_company → **❽ item_eligibility (Optional)**

## 2. Optional 레이어 원칙

### 2.1 선행 게이트 금지
- Item Eligibility는 ❶~❼ 레이어의 판단을 **차단하거나 선행하지 않습니다**.
- 모든 물품 질문에 직접생산확인 또는 중기경쟁제품 확인을 강제하지 않습니다.

### 2.2 호출 조건
- `item_eligibility_required = true`인 경우에만 호출됩니다.
- 트리거 조건은 `item_eligibility_trigger_policy_v0_1_4.md`에 정의됩니다.
- 트리거는 3등급(Explicit/Silent/Enrichment)으로 분류됩니다. 상세는 `item_eligibility_silent_trigger_policy.md`, `company_candidate_enrichment_policy.md` 참조.

### 2.3 결과의 성격
- Item Eligibility 결과는 **최종 결론이 아니라 후보 분류 정보**입니다.
- Answer Builder는 eligibility_context를 **참고 정보**로만 사용합니다.

## 3. 금지 행위 (7개)

| # | 금지 행위 | 위반 시 영향 |
|:-:|----------|-------------|
| P1 | 모든 물품 질문에 Item Eligibility 선행 호출 | 일반 금액·계약방식 질문에 불필요한 직생 확인 요구 |
| P2 | 직생 미확인으로 지역업체 후보 검색 차단 | 지역업체 수주 지원이라는 시스템 목적 훼손 |
| P3 | 직접생산확인 보유만으로 계약 가능 단정 | 금액·기관유형·계약방식 미검토 상태에서 오판 |
| P4 | 중기경쟁제품이 아닌 품목에 직생을 필수요건처럼 안내 | 실무상 불필요한 절차를 강요, 담당자 혼란 |
| P5 | 세부품명 미확정 상태에서 지역업체 검색 차단 | 품목명만으로도 지역업체 후보 검색은 가능해야 함 |
| P6 | 직생 미확인 업체를 자동 배제 | 미확인은 "증빙 확인 후보"로 분류해야 함 |
| P7 | 직생 유효만으로 계약 가능 단정 | 유효는 "우선 검토 후보"로만 분류해야 함 |

## 4. 허용 행위

| # | 허용 행위 | 조건 |
|:-:|----------|------|
| A1 | 사용자가 직생/중기경쟁을 명시적으로 질문한 경우 Item Eligibility 호출 | T1 Explicit |
| A2 | 세부품명번호가 제공된 경우 중기경쟁 여부 자동 확인 | T2 Explicit |
| A3 | 지역업체 후보표에 직생 상태 열 포함 (**Explicit 트리거 시만**) | T1/T2/T5 Explicit |
| A4 | 직생 유효 업체를 "우선 검토 후보"로 상위 정렬 | 단정이 아닌 후보 분류 |
| A5 | 직생 미확인 업체를 "증빙 확인 후보"로 표시 | 배제가 아닌 안내 |
| A6 | T3 Silent 발동 시 보조 문구 1줄만 답변 말미에 표시 | T3 Silent |
| A7 | T4 Enrichment 시 후보표에 optional column "직생 참고" 추가 | T4 Enrichment |

## 5. 레이어 간 독립성

```
❻ local_preference (지역업체 후보 검색)
    │
    │  ← 독립 실행. item_eligibility 결과와 무관하게 지역업체 검색 수행.
    │
    ▼
❼ policy_company (정책기업 특례)
    │
    │  ← 독립 실행. 사회적기업, 여성기업 등 특례 판단은 직생과 무관.
    │
    ▼
❽ item_eligibility (Optional)
    │
    │  ← item_eligibility_required = true일 때만 호출.
    │  ← 결과는 후보 분류 정보로만 Answer Builder에 전달.
    │
    ▼
Answer Builder (최종 답변 조립)
    └── ❶~❼ 결과 + (있으면) ❽ 결과를 종합하여 답변 생성
```

## 6. Answer Builder 결합 규칙

1. `item_eligibility_required = false`인 경우:
   - ❶~❼ 결과만으로 답변을 조립합니다.
   - 직생/중기경쟁 관련 문구를 답변에 포함하지 않습니다.

2. `item_eligibility_required = true`인 경우:
   - ❶~❼ 결과를 기반으로 답변을 조립합니다.
   - eligibility_context를 **별도 섹션**으로 답변에 추가합니다.
   - 직생 상태는 "우선 검토 후보" / "증빙 확인 후보" / "갱신 확인 필요" 등 `item_eligibility_answer_policy_v0_1_2.md`의 표현만 사용합니다.

## 7. 기존 문서와의 관계

| 문서 | 상태 | 비고 |
|------|:----:|------|
| `item_eligibility_rule_integration_plan.md` | superseded | Item Eligibility를 Step 1 선행으로 배치 → 본 정책에 의해 폐기 |
| `item_eligibility_rule_integration_plan_v0_1_2.md` | superseded | 처리 순서 1~9를 Item Eligibility 선행으로 정의 → 본 정책에 의해 폐기 |
| `item_eligibility_answer_policy_v0_1_2.md` | 유지 | 상태별 답변 전략은 그대로 적용 |
| `item_eligibility_lookup_policy_v0_1_2.md` | 유지 | Alias Resolution, 적격성 판별 로직은 트리거 충족 시 그대로 적용 |
| `item_eligibility_candidate_table_policy.md` | 유지 | 후보표 열 구성·정렬 우선순위는 트리거 충족 시 그대로 적용 |
| `item_eligibility_status_taxonomy.json` | 유지 | 상태 분류 체계는 그대로 적용 |
| `rule_engine_priority_order_v0_1.md` | 신규 | 8단계 우선순위 정의 (본 문서의 상위 문서) |
| `item_eligibility_trigger_policy_v0_1_3.md` | superseded | v0.1.4로 대체 |
| `item_eligibility_trigger_policy_v0_1_4.md` | **현행** | 트리거 3등급 체계 정의 (본 문서의 호출 조건 문서) |
| `item_eligibility_silent_trigger_policy.md` | **현행** | T3 Silent 등급 동작 규칙 |
| `company_candidate_enrichment_policy.md` | **현행** | T4 Enrichment 단계 정책 |
| `item_eligibility_trigger_test_cases_v0_1_4.md` | **현행** | 12건 테스트 케이스 |
