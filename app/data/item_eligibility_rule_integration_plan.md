# Item Eligibility Rule Integration Plan

본 문서는 기존 Phase 7-B의 거시적 법령 라우팅 체계(수요기관, 금액, 경로 등)와 새롭게 도입되는 **미시적 품목 단위(Item Eligibility) 판단 체계**를 통합하는 Rule Engine의 동작 시퀀스를 정의합니다.

## 1. 전제 조건
계약의 적법성 여부는 단일 요소만으로 판별되지 않습니다.
- **거시적 판단(Macro)**: `buyer_type`, `amount`, `procurement_route`, `contract_method`
- **미시적 판단(Micro)**: `detail_item_code`, `sme_competition`, `direct_production`

## 2. Rule Engine 통합 판정 시퀀스

**Step 1. Item Alias Resolution (품목명 정규화)**
사용자 질의에서 품목명이 감지되면 `item_alias_map`에서 매칭을 시도합니다. 매칭되는 `detail_item_code`가 단일하게 특정되지 않으면, 시스템은 더 이상의 적법성 판단을 멈추고 **추가 질의(후보군 제시)**를 반환합니다.

**Step 2. SME Competition & Direct Production 검증**
`detail_item_code`가 확정되면:
1. `sme_competition_product_item`에서 `is_sme_competition_product` 값과 현재 날짜(유효기간)를 검토.
2. 경쟁제품일 경우, `direct_production_requirement`에서 요구되는 설비/공정(직생 필수) 안내 텍스트를 Rule Context에 로드.

**Step 3. Company Certificate 교차 검증 (특정 업체가 언급된 경우)**
질의에 후보 업체(`company_id`)가 포함된 경우:
- `company_direct_production_cert_mapping`을 조회.
- 보유한 `cert_status`가 `valid`이고 유효기간 내에 있는지 교차 검증.
- 유효하지 않거나 데이터가 없을 시, "유효 확인되지 않음" 경고를 Context에 추가.

**Step 4. 거시적 기준과의 결합 (Final Overlay)**
위 3단계에서 도출된 품목의 "사전 적격성(Eligibility)" 정보와, 기존 로직인 `buyer_type` 및 `amount` 정보(예: 지방계약 수의계약 한도금액 충족 여부 등)를 결합하여 최종 답변을 생성합니다.

**Step 5. 최종 답변 반환**
(Answer Policy에 정의된 '단정적 판단 금지' 원칙을 준수한 문구로 반환)
