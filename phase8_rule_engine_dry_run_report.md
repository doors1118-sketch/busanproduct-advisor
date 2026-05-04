# Phase 8 Rule Engine Dry-Run Report

> **작성일**: 2026-05-04  
> **대상 스크립트**: `scripts/validate_phase8_rule_engine_dry_run.py`

---

## 1. 검증 개요

Gateway가 산출한 13개의 Mock Response(`GatewayResponse`)와 가상의 `original_request`(슬롯 모의 값)를 묶은 `RuleEngineInput`을 입력받아, Rule Engine이 8단계 매핑 로직을 통해 `DecisionContext`를 구조에 맞게 생성하는지 Dry-Run 테스트를 수행하였습니다.

본 테스트는 DB 쓰기, 외부 API 호출 등 일체의 환경 변경 없이(`No-Mutation` 정책 준수) 데이터 매핑 및 정책 적용 로직의 정합성을 확인하는 **mock 기반 검증**입니다. 실제 법령 판단의 완벽한 정확성은 이 스크립트의 검증 범위 밖이며, 후속 단계(통합 테스트)에서 확인될 예정입니다.

## 2. 검증 항목

1. **provisional_evaluation 처리**: 
   - `buyer_type_confidence`가 `"low"`일 때, `provisional_evaluation = true` 플래그가 설정되고 `assumption_warnings` 메시지가 생성되는지 확인
2. **Ambiguous 상태 처리 (TC-EX1)**:
   - `resolver_status`가 `"ambiguous"`일 때 `DecisionContext`의 `item_eligibility_grade`가 `"explicit"` 등 원본 `trigger_grade`를 유지하면서 `item_eligibility_status`는 `"ambiguous"`로 매핑되는지 확인
3. **Enrichment 독립성 비교 검증 (강화)**: 
   - `enrichment_applied = true`인 케이스에 대해 해당 값을 강제로 반전(False)시킨 복제 입력을 생성하여 Rule Engine을 재실행한 뒤, `contract_method_candidates`, `amount_threshold_met`, `local_preference_applicable` 값이 변하지 않음을 비교 검증
4. **Answer Builder 노출 정책 (trigger_grade)**: 
   - `DecisionContext.item_eligibility_grade`가 Gateway의 원본 `trigger_grade`에 맞게 매핑되는지 확인

## 3. 검증 결과

| 검증 항목 | 대상 TC | 결과 | 비고 |
|---|---|:---:|---|
| **Provisional 평가 (buyer_type)** | 13개 전체 | **PASS** | T1 등 confidence low 조건 작동 확인 |
| **Ambiguous 상태 처리** | TC-EX1 | **PASS** | `grade`와 `status`의 분리 매핑 작동 확인 |
| **Enrichment 독립성 비교** | TC-T4, T7, T9 | **PASS** | Enrichment 토글 전후 주요 판단 결과 동일 (`enrichment_judgment_effect="none"`) |
| **Trigger Grade 매핑** | 13개 전체 | **PASS** | Answer Builder 우선 참조 매핑 확인 |

### 최종 판정: **ALL PASS**

---

## 4. 결론

13개의 모든 테스트 케이스에 대해 Rule Engine의 Mock 기반 매핑 로직이 의도대로 동작함을 dry-run 수준에서 1차 확인하였습니다.
특히, `original_request` 슬롯을 통합한 `RuleEngineInput` 구조 하에서도 Enrichment 데이터가 주요 판단 결과에 영향을 주지 않으며, Ambiguous 케이스 처리가 정상적으로 매핑됨을 검증했습니다.
