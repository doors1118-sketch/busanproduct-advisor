# 모델 라우팅 정책 — 최종 Walkthrough 및 인수인계 문서

## 현재 프로젝트 전체 흐름
본 프로젝트는 부산 조달 챗봇의 안정성, 법적 무결성, 운영 효율성을 확보하기 위한 백엔드 구조 및 모델 라우팅 정책 고도화 작업입니다. 주로 아래의 방향으로 진행되었습니다:
1. 법적 근거가 명확하지 않은 답변 방지 (Fail-closed & Fallback Policy)
2. 모델 비용 최적화 및 속도 향상 (위험도 기반 Pro/Flash 라우팅)
3. 업체 후보 표기의 법적 무결성 확보 (조달등록 vs 종합쇼핑몰 vs 정책기업 등 5종 분류)

## 지금까지 완료된 항목
- **MCP fail-closed**: 조건부 통과
- **TC5 broad query early exit**: 통과
- **Flash fallback safety**: 조건부 통과
- **TC7 후보군 분류체계 5종 확장**: 조건부 통과 (shopping_mall_supplier, local_procurement_company, policy_company 분리 등 완료)
- **TC8 모델 라우팅 정적 정책**: CONDITIONAL_PASS (10/10 PASS)

## 아직 NOT_RUN / HOLD 상태인 항목
- **Runtime model execution**: NOT_RUN (Gemini 2.5 Pro 쿼터 미회복)
- **Gemini 2.5 Pro main path**: NOT_RUN
- **Innovation actual search/tool_result integration**: NOT_RUN
- **Production deployment**: HOLD

## 다음 세션에서 바로 실행할 순서
1. `Gemini 2.5 Pro` 쿼터 회복 확인
2. TC8 runtime 검증 실행 (`python run_tc8_routing.py` 등) 및 결과 JSON 확인
3. TC7 Pro main path 재검증
4. `innovation_product` 검색 연동 (API / tool_result 연결)
5. `priority_purchase_product` 데이터 소스 연결 여부 확인
6. 국세청(NTS) 영업상태 검증 로직 안정화
7. E2E 전체 검증 (Staging)

## TC8 Pro runtime 검증 스펙
다음 런타임 검증 시에는 실제 호출된 모델(`model_used`)이 기록되어야 하며, `pro_call_executed=true` 또는 `fallback_used=true`가 명확히 찍혀야 합니다.

### `claim_validation` 필수 필드
Fallback(`fallback_allowed=true`)이 허용되기 위해서는 아래 claim이 모두 검증을 통과해야 합니다.
- `law_article_claim`
- `amount_threshold_claim`
- `amount_value_claim`
- `sole_contract_claim`
- `one_person_quote_claim`

### 15개 런타임 필수 필드
런타임 결과 JSON에는 반드시 아래 필드가 포함되어야 합니다.
1. `model_selected`
2. `model_used`
3. `pro_call_executed`
4. `fallback_used`
5. `fallback_reason`
6. `legal_conclusion_allowed`
7. `legal_judgment_requested`
8. `legal_judgment_allowed`
9. `company_table_allowed`
10. `blocked_scope`
11. `legal_basis`
12. `claim_validation`
13. `final_answer_preview`
14. `pass`
15. `failure_reason`
