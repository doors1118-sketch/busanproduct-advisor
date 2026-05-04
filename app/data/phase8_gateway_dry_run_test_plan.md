# Phase 8 Gateway Dry-Run Test Plan

> **버전**: v0.1.0  
> **관련 문서**: `phase8_gateway_mock_responses_tc01_tc06.json`, `phase8_gateway_mock_responses_tc07_tc12.json`, `phase8_gateway_mock_responses_extra.json`  
> **준수 지침**: `phase7_no_mutation_policy.md`

---

## 1. 개요 및 테스트 목적

Phase 8 Gateway의 실제 연동(데이터베이스 및 LLM 파이프라인)을 수행하기 전, Mock 데이터를 활용하여 설계된 인터페이스의 정합성과 안정성을 검증합니다.

- Gateway 모듈이 Rule Engine 및 Answer Builder로 전달하는 JSON 응답(`GatewayResponse`)의 구조적 무결성 확인
- `RuleEngineInput`과 8단계 매핑 로직(`DecisionContext` 생성)의 동작 시나리오 검증
- Answer Builder의 상태 표시 우선순위(`trigger_grade` 참조 원칙) 및 판단 영향 금지(Enrichment 데이터) 정책의 올바른 작동 여부 확인

---

## 2. 테스트 환경 및 제약 사항

본 테스트는 **실제 API 연동 없이** 로컬 모의 환경(Dry-Run)에서만 실행해야 합니다.

1. **No-Mutation 원칙**: 실제 운영 DB(INSERT/UPDATE/DELETE) 접근 금지
2. **외부 통신 차단**: 법제처 API, NTS 연동 API, NCP 서버 연동 등 일체 금지
3. **LLM 배제**: 자연어 응답 생성 로직은 LLM 없이 데이터 확인만 수행
4. **실행 환경**: 로컬 테스트 스크립트로 3개 Mock JSON 파일을 읽어 들인 뒤, Rule Engine 스키마 기반의 파싱/검증만 수행합니다.

---

## 3. 테스트 시나리오 및 핵심 검증 대상

Phase 8 Mock Response로 분리된 총 13개 케이스를 대상으로 합니다.

| TC ID | 질문 요약 | 주요 검증 포인트 |
|---|---|---|
| **TC-T1** | 8천만원 수의계약 가능? | `not_triggered` 상태, `buyer_type` 임시 판단 처리(`provisional_evaluation=true`) |
| **TC-T2** | 부산업체 쓰는 방법 | `not_triggered` 상태, 지역제한 판단 분기 검증 |
| **TC-T3** | 컴퓨터 구매 방법 | `silent` 상태 발동. 보조 문구 1줄만 노출 (전면 노출 금지) |
| **TC-T4** | CCTV 업체 추천 | `silent` 상태 발동 + Enrichment(`general`). 검색 차단 없이 후보 노출 |
| **TC-T5** | CCTV 직생도 봐줘 | `explicit` 발동 (T1 키워드). 직생 전면 표시 및 정규 열 제공 |
| **TC-T6** | 세부품명 4617162201 | `explicit` 발동 (T2 품명). 품명 확정 기반 중기경쟁/직생 검토 수행 |
| **TC-T7** | 펌프 업체. 직생도 봐줘 | `explicit` 상태 + Enrichment(`specific_item`). 직생 데이터의 판단 영향 금지 검증 |
| **TC-T8** | 아까 컴퓨터 직생확인 | `silent` → `explicit` 승격 검증 (T1) |
| **TC-T9** | CCTV 업체 직생 | `explicit` + Enrichment(`candidate_items`). 후보별 직생 정규 열 검증 |
| **TC-T10** | 3억 공사 지역제한 가능? | 공사(`construction`)는 직생 적용 배제. `procedure_context` 필터 작동 |
| **TC-T11** | 부산 인쇄업체 추천 | `not_triggered` 상태. Enrichment 미적용 시 직생 열 누락 검증 |
| **TC-T12** | 노트북 업체 추천 | `silent` 상태. 직생 미확인이 업체 검색을 차단하지 않음 |
| **TC-EX1** | SW 중기경쟁 (ambiguous) | 복수 품명 후보, `ambiguous` 처리 및 세부품명 확정 유도 검증 |

---

## 4. 수행 절차

### 단계 1: Mock Data 파싱 및 검증
- 3개의 Mock JSON 파일(`tc01_tc06.json`, `tc07_tc12.json`, `extra.json`)을 파싱합니다.
- `phase8_gateway_response_schema.json` v0.1.1 기반으로 13개 `GatewayResponse` 객체의 유효성을 Strict 검증합니다.
- `request_id` 형식이 UUID v4인지 확인합니다.

### 단계 2: RuleEngineInput 구성
- 각 Mock 응답에 대응하는 가상의 `original_request` (슬롯 정보)를 결합하여 `RuleEngineInput` 객체를 생성합니다.

### 단계 3: Rule Engine 8단계 매핑 (Mocking)
- `RuleEngineInput`을 입력으로 하여 1~8단계 판단 매핑 코드를 모의 실행합니다.
- 각 TC별 `DecisionContext` 산출물을 생성합니다.

### 단계 4: Answer Builder 정책 검증
- 생성된 `DecisionContext`와 원본 `GatewayResponse`를 통해 다음을 검증합니다:
  - `enrichment_judgment_effect` 값이 항상 `"none"`인지 확인
  - `item_eligibility_grade` 값에 따라 올바른 노출 수준(섹션/보조문구/숨김)이 적용되는지 확인
  - `data_unavailable` 또는 `not_triggered` 상태에서 `context.trigger_grade` 직접 참조 시나리오가 방지되었는지 확인

---

## 5. 성공 기준 (Pass Criteria)

1. **스키마 정합성**: 13개 케이스 모두 JSON Schema 및 UUID 검증 에러 없이 파싱 성공
2. **Provisional 평가**: `buyer_type_confidence`가 `"low"`인 경우, `DecisionContext.provisional_evaluation`가 `true`로 설정되고 `assumption_warnings`가 올바르게 생성됨
3. **Enrichment 독립성**: Enrichment 데이터 존재 유무가 1~7단계(계약방식, 금액, 지역제한 등) 판단 결과에 영향을 주지 않음
4. **Trigger 우선 참조**: Answer Builder가 노출 여부 판단 시 `DecisionContext.item_eligibility_grade`를 우선 참조하고 규칙대로 처리함
