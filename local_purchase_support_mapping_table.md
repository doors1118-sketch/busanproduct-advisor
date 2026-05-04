# 지역업체 구매지원 제도 Mapping Table v0.2

| Rule ID | Category | Display Name | Law System | Contract Object | Amount Condition | Quote Type | Procurement Route | Safe Phrase | Review Status |
|---|---|---|---|---|---|---|---|---|---|
| R_DIRECT_GENERAL_SMALL_AMOUNT | direct_contract | 일반 소액수의계약 금액 기준 검토 |  |  |  | direct_contract_general |  | 일반 소액수의계약 금액 기준 확인 필요 | source_mapping_required |
| R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY | direct_contract | 일반 소액수의계약 우선 경로 배제 검토 |  |  | 50000000~ |  |  | 금액 초과에 따른 다른 계약방식 우선 검토 필요 | not_primary_route |
| R_DIRECT_ONE_PERSON_QUOTE | direct_contract | 1인 견적 수의계약 사유 검토 |  |  |  | one_person_quote |  | 1인 견적 수의계약 요건 확인 필요 | source_mapping_required |
| R_DIRECT_TWO_OR_MORE_QUOTES | direct_contract | 2인 이상 견적 수의계약 절차 검토 |  |  |  | two_or_more_quotes |  | 2인 이상 견적 제출 여부 확인 필요 | source_mapping_required |
| R_DIRECT_POLICY_COMPANY | direct_contract | 정책기업 특례 검토 |  |  |  |  |  | 업체 인증 유효성 및 특례 금액 기준 확인 필요 | source_mapping_required |
| R_DIRECT_TECH_PRODUCT | direct_contract | 기술개발제품·인증제품 특례 검토 |  |  |  |  |  | 제품 인증·지정 여부 확인 필요 | source_mapping_required |
| R_REGIONAL_RESTRICTION_GOODS | regional_restriction | 물품 지역제한 경쟁입찰 검토 |  | goods |  |  |  | 물품 지역제한 금액 기준 확인 필요 | source_mapping_required |
| R_REGIONAL_RESTRICTION_SERVICE | regional_restriction | 용역 지역제한 경쟁입찰 검토 |  | service |  |  |  | 용역 지역제한 금액 기준 확인 필요 | source_mapping_required |
| R_REGIONAL_RESTRICTION_CONSTRUCTION | regional_restriction | 공사 지역제한 경쟁입찰 검토 |  | construction |  |  |  | 공사 지역제한 금액 기준 확인 필요 | source_mapping_required |
| R_LIMITED_COMPETITION_REVIEW | regional_restriction | 제한경쟁입찰 검토 |  |  |  |  |  | 제한경쟁 사유 및 범위 확인 필요 | source_mapping_required |
| R_EVALUATION_CRITERIA_REVIEW | evaluation | 적격심사·종합평가·기술평가 기준 확인 |  |  |  |  |  | 평가기준표 확인 필요 | source_mapping_required |
| R_LOCAL_REGIONAL_JOINT_CONTRACT | joint_contract | 지방계약 기준 지역의무공동도급 검토 | local_contract | construction |  |  |  | 지방계약 공사 현장 및 금액 기준 확인 필요 | source_mapping_required |
| R_NATIONAL_REGIONAL_JOINT_CONTRACT | joint_contract | 국가계약 기준 지역의무공동도급 검토 | national_contract | construction |  |  |  | 국가계약 공사 현장 및 금액 기준 확인 필요 | source_mapping_required |
| R_PUBLIC_INSTITUTION_REGIONAL_JOINT_CONTRACT_CHECK | joint_contract | 공공기관 내부규정상 지역공동도급 기준 확인 |  | construction |  |  |  | 기관 자체 규정 확인 필요 | source_mapping_required |
| R_JOINT_CONTRACT_NOT_PRIMARY_GOODS | joint_contract | 물품 지역의무공동도급 우선 경로 배제 |  | goods |  |  |  | 공동수급 가능 여부는 별도 검토 필요 | not_primary_route |
| R_JOINT_CONTRACT_NOT_PRIMARY_SERVICE | joint_contract | 일반용역 지역의무공동도급 우선 경로 배제 |  | service |  |  |  | 용역 특성에 따른 공동수급 기준 별도 검토 필요 | not_primary_route |
| R_GOODS_REGIONAL_POINTS_NOT_PRIMARY | participation_points | 물품 지역업체 가점 우선 경로 배제 |  | goods |  |  |  | 물품 특성에 따른 평가 기준 확인 필요 | not_primary_route |
| R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK | participation_points | 용역 평가기준상 지역업체 참여도·가점 확인 |  | service |  |  |  | 세부 평가기준표 확인 필요 | source_mapping_required |
| R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK | participation_points | 공사 적격심사·종합평가·기술평가상 지역업체 참여도 확인 |  | construction |  |  |  | 평가기준별 배점 한도 확인 필요 | source_mapping_required |
| R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW | participation_points | MAS 2단계경쟁 지역업체 평가항목 검토 |  |  |  |  | mas | 평가방식·제안요청 기준 확인 필요 | evaluation_criteria_check_required |
| R_LOCAL_PRODUCT_PRIORITY | local_priority | 지역상품 우선구매 조례·시책 검토 |  | goods |  |  |  | 조례 적용 여부 확인 필요 | source_mapping_required |
| R_POLICY_COMPANY_PREFERENCE | policy_company | 정책기업 우대·우선구매 검토 |  |  |  |  |  | 유효한 정책기업 인증 여부 확인 필요 | source_mapping_required |
| R_SOCIAL_VALUE_PURCHASE_REVIEW | policy_company | 사회적경제기업·중증장애인생산품 등 우선구매 검토 |  |  |  |  |  | 우선구매 요건 및 증빙 확인 필요 | source_mapping_required |
| R_SHOPPING_MALL_ROUTE_CLASSIFICATION | shopping_mall | 종합쇼핑몰 등록 물품 경로 구분 |  |  |  |  | pps_shopping_mall | 종합쇼핑몰 등록 물품은 MAS 다수공급자계약인지 제3자단가계약인지 먼저 확인해야 합니다. | source_mapping_required |
| R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW | shopping_mall | 제3자단가계약 직접 납품요구 검토 |  |  |  |  | third_party_unit_price_contract | 제3자단가계약 규정 및 한도 금액 확인 필요 | source_mapping_required |
| R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT | shopping_mall | MAS 일반제품 5천만원 이상 기준 검토 |  |  | 50000000~ |  | mas | 2단계경쟁 적용 기준 금액 확인 필요 | source_mapping_required |
| R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION | shopping_mall | MAS 중소기업자간 경쟁제품 1억원 이상 기준 검토 |  |  | 100000000~ |  | mas | 2단계경쟁 적용 기준 금액 확인 필요 | source_mapping_required |
| R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL | shopping_mall | 중소기업 제조품목 5천만원 이상 1억원 미만 선택 적용 구간 검토 |  |  | 50000000~100000000 |  | mas | 선택적 2단계경쟁 적용 가능 여부 확인 필요 | source_mapping_required |
| R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW | shopping_mall | 2단계경쟁 대상 금액 미만 지역업체 후보 조회 |  |  |  |  | mas | 2단계경쟁 대상 금액 미만으로 확인되는 경우 종합쇼핑몰 등록 업체 중 지역업체 후보를 조회하고 납품요구 경로를 검토할 수 있습니다. | source_mapping_required |
| R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW | shopping_mall | MAS 2단계경쟁 종합평가·표준평가 방식 검토 |  |  |  |  | mas | 평가방식별 세부 기준 확인 필요 | source_mapping_required |
| R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP | shopping_mall | MAS·종합쇼핑몰 내 지역업체 후보 조회 |  |  |  |  | mas, pps_shopping_mall | 지역업체 검색 결과 확인 필요 | source_mapping_required |
| R_EXPLICIT_ITEM_ELIGIBILITY | item_eligibility | 중기경쟁제품·직접생산확인 추가 검토 |  |  |  |  |  | 증빙 확인 필요 | source_mapping_required |
| R_TECH_DEVELOPMENT_PRODUCT_REVIEW | item_eligibility | 기술개발제품·성능인증·혁신제품 확인 |  |  |  |  |  | 인증 유효성 확인 필요 | source_mapping_required |
| R_COMPANY_CANDIDATE_LOOKUP_GOODS | candidate_lookup | 물품 후보업체 조회 |  | goods |  |  |  | 후보 조회 필요 | source_mapping_required |
| R_COMPANY_CANDIDATE_LOOKUP_SERVICE | candidate_lookup | 용역 후보업체 조회 |  | service |  |  |  | 후보 조회 필요 | source_mapping_required |
| R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION | candidate_lookup | 공사 면허업체 후보 조회 |  | construction |  |  |  | 후보 조회 필요 | source_mapping_required |
| R_BUYER_TYPE_LOW_CONFIDENCE | validation | 기관유형 확인 필요 |  |  |  |  |  | 기관유형 확인 필요 | source_mapping_required |

## 금지 표현 정책
본 매핑 테이블의 어떠한 항목도 '계약 가능합니다', '구매 가능합니다', '지역제한 가능합니다', '수의계약 가능합니다', '낙찰 가능합니다'를 포함하지 않습니다.
