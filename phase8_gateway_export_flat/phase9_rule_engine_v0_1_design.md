# Phase 9 Rule Engine v0.1 Design

본 설계 문서는 `GatewayResponse`를 입력받아 Answer Builder가 사용할 안전하고 결정론적인 검토 컨텍스트(`DecisionContext`)를 생성하는 **Rule Engine v0.1의 구조**를 정의합니다.

## 1. 아키텍처 및 역할
- **역할**: Rule Engine은 **"최종 적격성 판단 엔진이 아닙니다."** 입력된 GatewayResponse를 기반으로 Answer Builder가 사용할 검토 상태, 적용 source, 누락 슬롯, 후속 조치, 노출 정책을 생성하는 "상태 매핑(State Mapping) 컴포넌트"입니다.
- **데이터 파이프라인**: 
  `GatewayResponse` $\rightarrow$ `RuleEngine` $\rightarrow$ `DecisionContext` $\rightarrow$ `Answer Builder`

## 2. No-Conclusion Policy (결론 금지 정책)
Rule Engine은 확정적인 적격성(예: Eligible/Ineligible) 판정을 내리지 않으며, 철저히 "검토 권고"와 "조건부 매핑" 수준의 상태값만 반환합니다.
- `legal_conclusion = "not_determined"`를 객체 생성 시 기본값으로 강제합니다.
- 어떠한 상황에서도 다음의 확정적 표현들이 Answer Builder 단계로 유입되거나 생성되도록 유도하는 지시자/상태값을 반환하지 않습니다:
  - "계약 가능합니다"
  - "구매 가능합니다"
  - "수의계약 가능합니다"
  - "지역제한 가능합니다"
  - "낙찰 가능합니다"

## 3. 핵심 상태 속성 (Review Outcome)
`GatewayResponse`의 상태들에 따라 Rule Engine은 다음 중 하나의 `review_outcome`을 부여합니다.
1. `review_candidate`: 조건이 대체로 충족되어 세부 검토가 권고되는 대상
2. `conditional_review`: 특정 조건(예: 인증서 갱신, 직접생산 확인 등)의 추가 확인이 필요한 대상
3. `manual_review_required`: 엣지 케이스, 복수 법령 충돌 또는 수동 판독이 필요한 대상
4. `insufficient_data`: `buyer_type`, `item_name` 등 필수 슬롯 누락으로 판단을 보류해야 하는 대상
5. `not_triggered`: 특별한 자격 심사 로직이 발동되지 않은 일반 조달 대상
6. `out_of_scope`: 관할 구역 외, 지원 불가 항목 등 명확한 스펙 아웃 대상
