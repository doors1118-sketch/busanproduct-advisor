# 지역업체 구매지원 제도 Mapping Table

이 표는 GatewayResponse 파라미터(계약목적물, 조달경로 등)에 따라 지역업체 구매지원 제도를 어떻게 식별하고 매핑하는지에 대한 기준을 명세합니다.

| Rule ID | 검토 대상 명칭 (display_name) | 매핑 조건 (Condition) | Answer Builder 노출 문구 (safe_phrase) | Action 권고 (suggested_action) |
| --- | --- | --- | --- | --- |
| **R_LOCAL_RESTRICT** | 지역제한 경쟁입찰 검토 | `contract_objects`: ["goods", "service", "construction"] | 금액·기관유형 기준 확인 필요 | 지역업체 참가를 위한 지역제한 요건 검토 필요 |
| **R_JOINT_CONTRACT** | 지역의무공동도급 검토 | `contract_objects`: ["construction"] | 공사 현장 및 금액 기준 확인 필요 | 지역업체 공동도급 비율 적용 여부 우선 검토 |
| **R_PARTICIPATION_POINTS**| 지역업체 참여도 가점 검토 | `contract_objects`: ["service", "construction"] | 적격심사 세부기준상 가점 여부 확인 필요 | 적격심사 시 지역업체 참여도 배점 적용 대상인지 검토 필요 |
| **R_LOCAL_PRIORITY** | 지역상품 우선구매 조례·시책 검토 | `contract_objects`: ["goods"] | 지역 조례 및 시책 우선 적용 범위 확인 필요 | 해당 지자체 우선구매 조례 적용 대상인지 확인 필요 |
| **R_DIRECT_CONTRACT** | 수의계약 활용 가능성 검토 | `contract_methods`: ["direct_contract"] | 수의계약 한도 금액 및 대상 기업 요건 확인 필요 | 지역업체와의 수의계약 한도액 내 포함 여부 우선 검토 |
| **R_POLICY_COMPANY** | 정책기업 우대·우선구매 검토 | 기본 적용 (조건 없음) | 정책기업 인증 유효성 및 기관별 의무 구매비율 확인 필요 | 여성기업, 장애인기업, 사회적기업 등 정책기업 우선구매 대상 여부 검토 필요 |
| **R_MAS_CANDIDATE** | MAS·종합쇼핑몰 내 지역업체 후보 활용 검토 | `procurement_routes`: ["mas", "pps_shopping_mall", "third_party_unit_price_contract"] | 종합쇼핑몰 등록 여부 및 2단계 경쟁 규정 확인 필요 | 종합쇼핑몰 내 지역업체 검색 및 2단계 경쟁 시 지역업체 제안 우선 검토 |
| **R_EXPLICIT_ITEM** | 품목별 중기경쟁제품·직접생산확인 추가 검토 | `item_trigger_grade`: "explicit" | 경쟁제품 요건 및 직접생산확인 유효성 증빙 확인 필요 | 중소기업자간 경쟁제품 지정 여부 및 직접생산확인증명서 보유 여부 증빙 확인 필요 |
| **R_BUYER_TYPE_LOW_CONFIDENCE**| 기관유형 확인 필요 | `buyer_type_confidence`: "low" | 기관유형에 따른 정확한 법적 기준 확인 필요 | 적용할 법령 확정을 위해 발주기관의 유형을 정확히 확인해야 함 |

## 금지 사항 명시
- 위 모든 노출 문구에는 "가능합니다", "계약 가능합니다", "낙찰 가능합니다" 등의 확정적 결론을 내포하는 어휘가 단 한 글자도 포함되어서는 안 됩니다.
- 오직 "검토 필요", "확인 필요", "우선 검토", "증빙 확인 필요" 수준의 가이던스만 제공합니다.
