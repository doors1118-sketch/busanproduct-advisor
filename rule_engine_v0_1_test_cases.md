# Rule Engine v0.1 Test Cases (BDD)

이 문서는 Rule Engine이 생성하는 `DecisionContext`의 무결성과 금지된 결론 도출(No-Conclusion) 방어 체계를 검증하기 위한 핵심 시나리오입니다. 모든 테스트는 Pytest를 통해 자동화되어야 합니다.

## 시나리오 1: 필수 정보 부족 (buyer_type 미상)
- **Given**: GatewayResponse 내 `buyer_type_confidence`가 `"low"`이고 `buyer_type_assumed` 속성이 적용됨
- **When**: Rule Engine이 매핑 로직을 수행함
- **Then**: 
  - `DecisionContext.review_outcome`은 `"insufficient_data"` 여야 한다. (다른 조건이 만족하더라도 우선 적용)
  - `missing_required_slots`에 `"buyer_type"`이 포함되어야 한다.
  - `legal_conclusion`은 반드시 `"not_determined"`여야 한다.

## 시나리오 2: 중소기업자간 경쟁제품 + 유효한 직생증명서 (MAS 오버레이)
- **Given**: `overlay_applied=True`, `item.resolver_status="resolved"`, `is_sme_competition=True`, `company_cert_status="valid"`
- **When**: Rule Engine이 매핑 로직을 수행함
- **Then**:
  - `review_outcome`은 `"review_candidate"`여야 한다.
  - `dual_routing_active`는 `True`여야 한다.
  - `route_directive`는 `"base_law_plus_pps_overlay_review"`여야 한다.
  - `item_action_required`는 `"verify_direct_production_cert"`여야 한다.
  - `legal_conclusion`은 반드시 `"not_determined"`여야 한다.
  - `enrichment_judgment_effect`는 `"none"`여야 한다.

## 시나리오 3: 엣지 케이스 (복수 품목 혼선 / Ambiguous)
- **Given**: `item.resolver_status="ambiguous"` 및 다중 `detail_item_candidates` 반환
- **When**: Rule Engine이 매핑 로직을 수행함
- **Then**:
  - `review_outcome`은 `"manual_review_required"`여야 한다.
  - `manual_review_reasons`에 `"detail_item_code_ambiguous"`가 포함되어야 한다.
  - `legal_conclusion`은 반드시 `"not_determined"`여야 한다.

## 🚫 [Negative Test] 확정적 금지 표현 생성 통제
Rule Engine을 거쳐 Answer Builder에 주입될 **`DecisionContext`의 전체 문자열화(Stringify)된 결과 내부에** 어떠한 경우에도 다음의 금지 표현이 포함되어서는 **안 된다.**
- `"계약 가능합니다"`
- `"구매 가능합니다"`
- `"수의계약 가능합니다"`
- `"지역제한 가능합니다"`
- `"낙찰 가능합니다"`
(해당 테스트는 `test_rule_engine_forbidden_words`의 형태로 `str(decision_context)`에 대한 정규식 검증을 통해 CI 단계에서 완전히 차단되어야 합니다.)
