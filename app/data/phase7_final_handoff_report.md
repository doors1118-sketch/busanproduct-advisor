# Phase 7 Final Baseline Freeze — Handoff Report

> **작성일**: 2026-05-04  
> **상태**: `frozen_for_phase8_gateway_design`  
> **다음 단계**: Phase 8 Internal Legal MCP Gateway 설계

---

## 1. Phase 7 Final Baseline 요약

Phase 7은 법령판단 DB, 업데이트 파이프라인, Rule Engine 우선순위, Item Eligibility Optional Layer를 기준선으로 고정하는 단계입니다.

| 항목 | 상태 |
|------|:----:|
| 법령판단 DB (legal_db_v0_1_3.sqlite) | ✅ Frozen |
| Legal Update Pipeline v0.1.3 dry-run | ✅ PASS |
| Rule Engine 8단계 우선순위 | ✅ Frozen |
| Item Eligibility v0.1.4 (Optional Layer + Trigger 3등급) | ✅ Frozen |
| Answer Builder 정합성 수정 (trigger_grade별 노출) | ✅ 완료 |
| No-Mutation Policy | ✅ 작성 완료 |

---

## 2. 고정된 법령판단 DB 상태

| 지표 | 값 |
|------|---:|
| 기준 DB | `legal_db_v0_1_3.sqlite` |
| DB 크기 | 397,312 bytes |
| total_sources | 217 |
| active_for_rule | 63 |
| active_for_procedure | 15 |

### 주요 속성 분리 상태

- **activation_mode**: 모든 active source에 설정 완료. activation_mode 없는 active source는 허용하지 않음.
- **procedure_only**: `active_for_rule=false`, `active_for_procedure=true`, `judgment_eligible=false`로 분리 완료. Rule Engine 판단 로직에서 완전 배제.
- **wrong_match / needs_manual_source**: 자동 판단에서 제외. 수동 검토 대기 상태.
- **procurement_route_layer**: 조달청 경로 Overlay 정책 분리 완료.

---

## 3. 고정된 업데이트 파이프라인 상태

| 항목 | 값 |
|------|------|
| 파이프라인 버전 | v0.1.3 |
| dry-run 상태 | PASS |
| dry-run 리포트 | `legal_update_pipeline_dry_run_report_v0_1_3.json` |
| 정책 문서 | `legal_update_policy.md` |

### 원천 분류

| 분류 | 수집 방법 | 갱신 주기 |
|------|-----------|-----------|
| 법령 (법률, 시행령, 시행규칙) | 법제처 API (`law`) | Daily (메타) / Weekly (전문) |
| 행정규칙 (훈령, 고시, 예규) | 법제처 API (`admrul`) | Daily (메타) / Weekly (전문) |
| 지방계약 핵심 PDF 2건 | 수동 (`pdf_manual`) | Weekly (메타) / Monthly (전문) |

### PDF Manual 관리 대상 (2건)

1. **지방자치단체 입찰 및 계약집행기준** (행정안전부 예규)
2. **지방자치단체 입찰시 낙찰자 결정기준** (행정안전부 예규)

관리 정책:
- `metadata_watch_frequency` = weekly
- `full_text_refresh_frequency` = monthly
- `source_refresh_method` = pdf_manual
- `law_api_target` = none
- 상세: `manual_pdf_metadata_watch_policy.md`

---

## 4. 고정된 Rule Engine 우선순위

```
❶ buyer_type (기관유형 식별)
❷ contract_object (계약목적물 분류)
❸ amount (추정가격·예정가격 확인)
❹ procurement_route (조달경로 판별)
❺ contract_method (계약방식 판별)
❻ local_preference (지역제한·지역업체 우대)
❼ policy_company / certification (정책기업·인증 특례)
❽ item_eligibility (조건부 Optional Layer)
```

- ❶~❼은 항상 실행
- ❽은 트리거 조건 충족 시에만 호출
- 정의 문서: `rule_engine_priority_order_v0_1.md`

---

## 5. Item Eligibility Optional Layer v0.1.4 요약

### 핵심 원칙
- Item Eligibility는 전체 계약판단의 **선행 게이트가 아닙니다**.
- `item_eligibility_required = true`일 때만 호출되는 **조건부 레이어**입니다.

### 트리거 3등급 체계

| 등급 | 트리거 | 답변 노출 | 후보표 직생 열 |
|:----:|--------|:---------:|:--------------:|
| **Explicit** | T1 (키워드), T2 (세부품명), T5 (계약경로) | 별도 섹션 | 정규 열 전면 표시 |
| **Silent** | T3 (alias_map 중기경쟁 후보 감지) | 보조 문구 1줄만 | 비표시 |
| **Enrichment** | T4 (업체 직생 데이터 존재) | 미표시 | optional column |

### 관련 문서
| 문서 | 역할 |
|------|------|
| `item_eligibility_optional_layer_policy.md` | Optional Layer 원칙, Answer Builder 결합 규칙 |
| `item_eligibility_trigger_policy_v0_1_4.md` | 트리거 3등급 체계 정의 |
| `item_eligibility_silent_trigger_policy.md` | T3 Silent 동작 규칙 |
| `company_candidate_enrichment_policy.md` | T4 Enrichment 단계 정책 |
| `item_eligibility_answer_policy_v0_1_2.md` | 상태별 답변 전략 |
| `item_eligibility_trigger_test_cases_v0_1_4.md` | 12건 테스트 케이스 |

---

## 6. T3 Silent / T4 Enrichment 정합성 보완 결과

### 수정 내역

`item_eligibility_optional_layer_policy.md`의 **§6 Answer Builder 결합 규칙**을 수정했습니다.

**수정 전** (v0.1.3 잔재):
- `item_eligibility_required = true`이면 일률적으로 eligibility_context를 별도 섹션으로 답변에 추가

**수정 후** (v0.1.4 정합):
- `trigger_grade`에 따라 4단계 노출 차등 적용:
  - **미발동**: 직생/중기경쟁 문구 미포함
  - **Explicit**: 별도 섹션 + 후보표 정규 열
  - **Silent**: 보조 문구 1줄만 + 후보표 직생 열 비표시
  - **Enrichment**: 답변 미언급 + 후보표 optional column만

이 수정으로 T3 Silent 트리거가 발동되어도 답변에 직생/중기경쟁이 전면 노출되는 문제가 방지됩니다.

---

## 7. Phase 8 Gateway로 넘길 입력 조건

Phase 8 Internal Legal MCP Gateway 설계에 필요한 입력물:

| 입력물 | 용도 |
|--------|------|
| `legal_db_v0_1_3.sqlite` | Gateway가 조회할 법령 DB |
| `legal_source_registry.json` | 법령 소스 메타데이터 |
| `rule_engine_priority_order_v0_1.md` | Gateway 출력을 소비할 Rule Engine 구조 |
| `item_eligibility_trigger_policy_v0_1_4.md` | Gateway가 eligibility context를 넘겨야 하는 조건 |
| `procurement_route_layer_policy.md` | 조달경로 Overlay 조건 |
| `local_public_institution_routing_policy.md` | 기관유형별 라우팅 조건 |
| `phase7_final_baseline_manifest.json` | 기준선 전체 inventory |
| `phase7_no_mutation_policy.md` | Gateway 설계 중 변경 금지 사항 |

---

## 8. 아직 하지 말아야 할 작업

| # | 금지 작업 | 이유 |
|:-:|----------|------|
| 1 | 운영 DB 변경 | Baseline frozen |
| 2 | `legal_db_v0_1_3.sqlite` 스키마 변경 | Baseline frozen |
| 3 | `active_for_rule` / `active_for_procedure` 임의 변경 | 판단 근거 오염 |
| 4 | `procedure_only`를 판단근거로 승격 | 절차용 전용 원칙 위반 |
| 5 | Item Eligibility를 선행 게이트로 재배치 | Optional Layer 원칙 위반 |
| 6 | T3를 Explicit으로 재승격 | Silent 과활성화 방지 위반 |
| 7 | T4를 초기 라우팅 트리거로 재배치 | Enrichment 분리 원칙 위반 |
| 8 | scheduler 등록 | 자동 실행 금지 |
| 9 | 실제 외부 API 호출 (law API, admrul API 포함) | 외부 연동 금지 |
| 10 | Production 배포 | 배포 금지 |
| 11 | 실제 원문 refresh | 데이터 변경 금지 |

---

## 9. Phase 8에서 해야 할 작업

### Phase 8 Internal Legal MCP Gateway

| # | 작업 | 설명 |
|:-:|------|------|
| 1 | Gateway 인터페이스 설계 | read-only 조회 API 스펙 정의 |
| 2 | Source Context Lookup 설계 | legal_db에서 source/route/item/company context 조회 |
| 3 | Route Layer Resolution 설계 | buyer_type → 기본 법령체계, procurement_route → Overlay 해소 |
| 4 | Item Eligibility Context 설계 | 트리거 판정 + eligibility_context 생성 로직 |
| 5 | Mock Response 정의 | 테스트용 mock response 구조 정의 |
| 6 | Gateway-Rule Engine 연동 인터페이스 | Gateway 출력 → Rule Engine 입력 매핑 |
| 7 | dry-run 테스트 설계 | Gateway 조회 결과의 정합성 검증 |

### Gateway 원칙
- **read-only**: DB write 금지
- **판단 금지**: 법적 결론 생성 금지
- **LLM 답변 생성 금지**: 조회 결과만 반환
- **안전한 조회 계층**: Rule Engine 이전 단계로만 동작

---

## 10. 회귀 테스트 기준

Phase 8 설계 중 또는 향후 Baseline 변경 시 아래 12건의 테스트를 회귀 검증해야 합니다.

| TC | 질문 유형 | 트리거 등급 | 핵심 검증 |
|:--:|-----------|:----------:|-----------|
| T1 | 금액·계약방식 | 미발동 | 직생 없이 금액 먼저 |
| T2 | 지역업체 범용 | 미발동 | 지역제한·정책기업 우선 |
| T3 | 일반 품목명 | Silent | 보조 문구 1줄만 |
| T4 | 업체 추천 | Silent + Enrichment | 검색 차단 금지, optional column |
| T5 | 직생 명시 | Explicit | 별도 섹션 전면 표시 |
| T6 | 세부품명 명시 | Explicit | 중기경쟁 검토 수행 |
| T7 | 업체 추천 (비경쟁) | Enrichment만 | 계약 판단 불변 |
| T8 | Silent → Explicit 전환 | 승격 | 2차 질문에서 전면 표시 |
| T9 | Explicit + Enrichment | Explicit 우선 | 정규 열로 전면 표시 |
| T10 | 공사 | 미발동 | 직생 완전 무관 |
| T11 | 업체 추천 (직생 0건) | Enrichment 미표시 | 열 자체 없음 |
| T12 | 품목 + 업체 검색 | Silent | 검색 차단 금지 |

테스트 상세: `item_eligibility_trigger_test_cases_v0_1_4.md`
