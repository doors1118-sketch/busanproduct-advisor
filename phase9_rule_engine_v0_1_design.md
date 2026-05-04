# Phase 9 Rule Engine v0.1 Design

본 설계 문서는 `GatewayResponse`를 입력받아 Answer Builder가 사용할 안전하고 결정론적인 검토 컨텍스트(`DecisionContext`)를 생성하는 **Rule Engine v0.1의 구조**를 정의합니다.

## 1. 아키텍처 및 역할
- **역할**: Rule Engine은 **"최종 적격성 결론 생성기가 아니라, Answer Builder 제어 컨텍스트 생성기입니다."** 입력된 GatewayResponse를 기반으로 Answer Builder가 생성할 문장의 방향(검토 상태, 적용 source, 누락 슬롯, 후속 조치, 노출 정책)을 조율하는 역할만 담당합니다.
- **데이터 파이프라인**: 
  `GatewayResponse` $\rightarrow$ `RuleEngine` $\rightarrow$ `DecisionContext` $\rightarrow$ `Answer Builder`

## 2. No-Conclusion Policy (결론 금지 정책)
Rule Engine은 확정적인 적격성 판정을 내리지 않으며, "검토 권고"와 "조건부 매핑" 수준의 상태값만 반환합니다.
- `legal_conclusion = "not_determined"`를 객체 생성 시 기본값으로 강제하며, 타입 체계에서부터 `Literal["not_determined"]`로 묶어 변경을 원천 차단합니다.
- 어떠한 상황에서도 다음의 확정적 표현들이 DecisionContext의 전체 문자열 내부 등 어딘가에 생성되도록 유도하지 않습니다:
  - "계약 가능합니다", "구매 가능합니다", "수의계약 가능합니다", "지역제한 가능합니다", "낙찰 가능합니다"

## 3. 핵심 설계 정책
1. **상태 분리 (Source Separation)**
   - 판단 근거 법령(`applied_source_ids`), 오버레이 법령(`overlay_source_ids`), 단순 안내용 절차(`procedure_source_ids`)를 리스트 레벨에서 철저히 분리합니다.
   - 특히 `procedure_context`는 Judgment Source(판단 근거)로 절대 사용하지 않으며, 오직 `procedure_source_ids`로 분리 매핑되거나 단순 Pass-through로 처리됩니다.
2. **Enrichment 영향 배제**
   - Company Enrichment Data(업체 정보 부가 데이터)는 참고용일 뿐, **절대로 `review_outcome`의 최종 상태를 변경(승급/강등)시키지 않습니다**. 이에 따라 `enrichment_judgment_effect = "none"` 정책을 강제합니다.

## 4. 핵심 상태 속성 (Review Outcome)
`GatewayResponse`의 상태들에 따라 Rule Engine은 다음 중 하나의 `review_outcome`을 우선순위에 따라 부여합니다.
1. `out_of_scope`: 관할 구역 외, 지원 불가 항목 등 명확한 스펙 아웃 대상
2. `insufficient_data`: `buyer_type` 누락 등 판단 보류가 불가피한 대상
3. `manual_review_required`: 엣지 케이스, 복수 법령 충돌 또는 수동 판독이 필요한 대상
4. `conditional_review`: 특정 조건의 갱신/추가 확인이 필요한 대상
5. `review_candidate`: 조건이 대체로 충족되어 세부 검토가 권고되는 정상 대상
6. `not_triggered`: 특별한 자격 심사 로직이 발동되지 않은 일반 대상
