# 지역업체 구매지원 제도 Mapping Table v0.2

| Rule ID | Category | Display Name | Law System | Contract Object | Contract Subtype | Amount Condition | Quote Type | Procurement Route | Evaluation Method | Numeric Basis | Legal Basis Source IDs | Review Status | Safe Phrase | Required Checks | Candidate Lookup Link |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| R_DIRECT_GENERAL_SMALL_AMOUNT | direct_contract | 일반 소액수의계약 금액 기준 검토 |  |  |  |  | direct_contract_general |  |  | Yes |  | source_mapping_required | 일반 소액수의계약 금액 기준 확인 필요 | 적용 법체계 확인<br>추정가격 확인<br>일반 소액수의계약 한도 확인 |  |
| R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY | direct_contract | 일반 소액수의계약 우선 경로 배제 검토 |  |  |  | exceeds_general_small_direct_threshold |  |  |  | Yes |  | not_primary_route | 금액 초과에 따른 다른 계약방식 우선 검토 필요 | 추정가격 확인<br>소액수의계약 한도 초과 여부 확인 |  |
| R_DIRECT_ONE_PERSON_QUOTE | direct_contract | 1인 견적 수의계약 사유 검토 |  |  |  |  | one_person_quote |  |  |  |  | source_mapping_required | 1인 견적 수의계약 요건 확인 필요 | 업체유형 확인<br>계약목적물 기준 부합 여부 확인<br>1인 견적 사유 해당 여부 확인 |  |
| R_DIRECT_TWO_OR_MORE_QUOTES | direct_contract | 2인 이상 견적 수의계약 절차 검토 |  |  |  |  | two_or_more_quotes |  |  |  |  | source_mapping_required | 2인 이상 견적 제출 여부 확인 필요 | 2인 이상 견적 대상 여부 확인<br>수의계약 배제사유 확인 |  |
| R_DIRECT_POLICY_COMPANY | direct_contract | 정책기업 특례 검토 |  | goods, service, construction |  | policy_company_check_relevant |  |  |  |  |  | source_mapping_required | 업체 인증 유효성 및 특례 금액 기준 확인 필요 | 유효한 정책기업 인증 여부 확인<br>특례 금액 기준 부합 여부 확인 |  |
| R_DIRECT_TECH_PRODUCT | direct_contract | 기술개발제품·인증제품 특례 검토 |  | goods |  | product_certification_check_relevant |  |  |  |  |  | source_mapping_required | 제품 인증·지정 여부 확인 필요 | 제품 인증 유효기간 확인<br>특례 계약 대상 제품 확인 |  |
| R_REGIONAL_RESTRICTION_GOODS | regional_restriction | 물품 지역제한 경쟁입찰 검토 |  | goods |  |  |  |  |  |  |  | source_mapping_required | 물품 지역제한 금액 기준 확인 필요 | 물품 지역제한 기준금액 확인<br>주된 영업소 요건 확인 |  |
| R_REGIONAL_RESTRICTION_SERVICE | regional_restriction | 용역 지역제한 경쟁입찰 검토 |  | service |  |  |  |  |  |  |  | source_mapping_required | 용역 지역제한 금액 기준 확인 필요 | 용역 지역제한 기준금액 확인<br>주된 영업소 요건 확인 |  |
| R_REGIONAL_RESTRICTION_CONSTRUCTION | regional_restriction | 공사 지역제한 경쟁입찰 검토 |  | construction |  |  |  |  |  |  |  | source_mapping_required | 공사 지역제한 금액 기준 확인 필요 | 공사 지역제한 기준금액 확인<br>주된 영업소 요건 확인 |  |
| R_LIMITED_COMPETITION_REVIEW | regional_restriction | 제한경쟁입찰 검토 |  |  |  |  |  |  |  |  |  | source_mapping_required | 제한경쟁 사유 및 범위 확인 필요 | 제한경쟁입찰 사유 해당 여부 확인<br>부당한 제한 여부 확인 |  |
| R_EVALUATION_CRITERIA_REVIEW | evaluation | 적격심사·종합평가·기술평가 기준 확인 |  |  |  |  |  |  | qualification_review, comprehensive_evaluation, technical_evaluation |  |  | source_mapping_required | 평가기준표 확인 필요 | 세부 평가기준표 확인<br>지역업체 지원 배점 확인 |  |
| R_LOCAL_REGIONAL_JOINT_CONTRACT | joint_contract | 지방계약 기준 지역의무공동도급 검토 | local_contract | construction |  |  |  |  |  | Yes |  | source_mapping_required | 지방계약 공사 현장 및 금액 기준 확인 필요 | 공사 현장 소재지 확인<br>지역의무공동도급 대상 금액인지 확인 |  |
| R_NATIONAL_REGIONAL_JOINT_CONTRACT | joint_contract | 국가계약 기준 지역의무공동도급 검토 | national_contract | construction |  |  |  |  |  | Yes |  | source_mapping_required | 국가계약 공사 현장 및 금액 기준 확인 필요 | 국가계약 적용 여부 확인<br>고시 금액 미만 여부 확인 |  |
| R_PUBLIC_INSTITUTION_REGIONAL_JOINT_CONTRACT_CHECK | joint_contract | 공공기관 내부규정상 지역공동도급 기준 확인 |  | construction |  |  |  |  |  |  |  | source_mapping_required | 기관 자체 규정 확인 필요 | 해당 기관의 내부 계약규정 확인<br>지역업체 공동도급 특례 유무 확인 |  |
| R_JOINT_CONTRACT_NOT_PRIMARY_GOODS | joint_contract | 물품 지역의무공동도급 우선 경로 배제 |  | goods |  |  |  |  |  |  |  | not_primary_route | 공동수급 가능 여부는 별도 검토 필요 | 물품 성격 확인<br>공동수급 필요성 별도 검토 |  |
| R_JOINT_CONTRACT_NOT_PRIMARY_SERVICE | joint_contract | 일반용역 지역의무공동도급 우선 경로 배제 |  | service | general_service |  |  |  |  |  |  | not_primary_route | 용역 특성에 따른 공동수급 기준 별도 검토 필요 | 용역 유형 확인<br>공동계약 적용 타당성 확인 |  |
| R_GOODS_REGIONAL_POINTS_NOT_PRIMARY | participation_points | 물품 지역업체 가점 우선 경로 배제 |  | goods |  |  |  |  |  |  |  | not_primary_route | 물품 특성에 따른 평가 기준 확인 필요 | 계약목적물 물품 여부 확인<br>적격심사 항목 중 물품 관련 배점 확인 |  |
| R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK | participation_points | 용역 평가기준상 지역업체 참여도·가점 확인 |  | service |  |  |  |  | negotiated_contract, proposal_evaluation, qualification_review |  |  | source_mapping_required | 세부 평가기준표 확인 필요 | 평가기준에 지역업체 배점 있는지 확인<br>공동수급 구성 여부 확인 |  |
| R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK | participation_points | 공사 적격심사·종합평가·기술평가상 지역업체 참여도 확인 |  | construction |  |  |  |  |  |  |  | source_mapping_required | 평가기준별 배점 한도 확인 필요 | 공사 심사기준상 지역업체 참여 비율표 확인<br>가점 부여 한도 확인 |  |
| R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW | participation_points | MAS 2단계경쟁 지역업체 평가항목 검토 |  |  |  |  |  | mas | mas_comprehensive | Yes |  | evaluation_criteria_check_required | 평가방식·제안요청 기준 확인 필요 | 2단계경쟁 종합평가방식 채택 여부 확인<br>제안요청서 지역업체 항목 포함 여부 확인 |  |
| R_LOCAL_PRODUCT_PRIORITY | local_priority | 지역상품 우선구매 조례·시책 검토 |  | goods |  |  |  |  |  |  |  | source_mapping_required | 조례 적용 여부 확인 필요 | 소관 지자체 조례 존재 여부 확인<br>우선구매 대상 상품에 해당 여부 확인 |  |
| R_POLICY_COMPANY_PREFERENCE | policy_company | 정책기업 우대·우선구매 검토 |  | goods, service, construction |  |  |  |  |  |  |  | source_mapping_required | 유효한 정책기업 인증 여부 확인 필요 | 우선구매 목표액 달성 여부 확인<br>정책기업 유효 인증 확인 |  |
| R_SOCIAL_VALUE_PURCHASE_REVIEW | policy_company | 사회적경제기업·중증장애인생산품 등 우선구매 검토 |  | goods, service, construction |  |  |  |  |  |  |  | source_mapping_required | 우선구매 요건 및 증빙 확인 필요 | 중증장애인생산품 지정 여부 확인<br>사회적경제기업 인증 여부 확인 |  |
| R_SHOPPING_MALL_ROUTE_CLASSIFICATION | shopping_mall | 종합쇼핑몰 등록 물품 경로 구분 |  |  |  |  |  | pps_shopping_mall |  |  |  | source_mapping_required | 종합쇼핑몰 등록 물품은 MAS 다수공급자계약인지 제3자단가계약인지 먼저 확인해야 합니다. | 해당 물품이 MAS인지 제3자단가계약인지 구분<br>경로별 납품요구 기준 확인 |  |
| R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW | shopping_mall | 제3자단가계약 직접 납품요구 검토 |  |  |  |  |  | third_party_unit_price_contract |  |  |  | source_mapping_required | 제3자단가계약 규정 및 한도 금액 확인 필요 | 제3자단가계약 규정 적용 여부 확인<br>직접 납품요구 가능 금액 확인 |  |
| R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT | shopping_mall | MAS 일반제품 2단계경쟁 기준 검토 |  |  |  |  |  | mas |  | Yes |  | source_mapping_required | 2단계경쟁 적용 기준 금액 확인 필요 | MAS 일반제품 요건 확인<br>기준금액 이상/미만 여부 확인 |  |
| R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION | shopping_mall | MAS 중소기업자간 경쟁제품 2단계경쟁 기준 검토 |  |  |  |  |  | mas |  | Yes |  | source_mapping_required | 2단계경쟁 적용 기준 금액 확인 필요 | 중소기업자간 경쟁제품 요건 확인<br>기준금액 이상/미만 여부 확인 |  |
| R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL | shopping_mall | 중소기업 제조품목 선택 적용 구간 검토 |  |  |  |  |  | mas |  | Yes |  | source_mapping_required | 선택적 2단계경쟁 적용 가능 여부 확인 필요 | 중소기업 제조물품 여부 확인<br>선택적 2단계경쟁 구간 여부 확인 |  |
| R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW | shopping_mall | 2단계경쟁 대상 금액 미만 지역업체 후보 조회 |  |  |  | below_second_stage_threshold |  | mas |  |  |  | source_mapping_required | 2단계경쟁 대상 금액 미만으로 확인되는 경우 종합쇼핑몰 등록 업체 중 지역업체 후보를 조회하고 납품요구 경로를 검토할 수 있습니다. | 금액 기준 미달 여부 재확인<br>지역업체 후보 검색 | shopping_mall_local_supplier |
| R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW | shopping_mall | MAS 2단계경쟁 종합평가·표준평가 방식 검토 |  |  |  |  |  | mas |  |  |  | source_mapping_required | 평가방식별 세부 기준 확인 필요 | 2단계경쟁 평가방식 선택<br>방식별 지역업체 유불리 판단 |  |
| R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP | shopping_mall | MAS·종합쇼핑몰 내 지역업체 후보 조회 |  |  |  |  |  | mas, pps_shopping_mall |  |  |  | company_api_mapping_required | 지역업체 검색 결과 확인 필요 | 지역 내 업체 수 파악<br>제안 조건 부합 업체 확인 | shopping_mall_local_supplier |
| R_EXPLICIT_ITEM_ELIGIBILITY | item_eligibility | 중기경쟁제품·직접생산확인 추가 검토 |  |  |  |  |  |  |  |  |  | source_mapping_required | 증빙 확인 필요 | 직생증명서 유효성 확인<br>중소기업자간 경쟁제품 고시 확인 |  |
| R_TECH_DEVELOPMENT_PRODUCT_REVIEW | item_eligibility | 기술개발제품·성능인증·혁신제품 확인 |  | goods, service |  |  |  |  |  |  |  | source_mapping_required | 인증 유효성 확인 필요 | 기술개발제품 인증서 유효기간 확인<br>성능인증 범위 확인 |  |
| R_COMPANY_CANDIDATE_LOOKUP_GOODS | candidate_lookup | 물품 후보업체 조회 |  | goods |  |  |  |  |  |  |  | company_api_mapping_required | 후보 조회 필요 | 물품 관련 지역 조건 설정<br>품목 분류코드 매핑 확인 |  |
| R_COMPANY_CANDIDATE_LOOKUP_SERVICE | candidate_lookup | 용역 후보업체 조회 |  | service |  |  |  |  |  |  |  | company_api_mapping_required | 후보 조회 필요 | 용역 분야별 실적 확인<br>지역 조건 설정 |  |
| R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION | candidate_lookup | 공사 면허업체 후보 조회 |  | construction |  |  |  |  |  |  |  | company_api_mapping_required | 후보 조회 필요 | 공종별 면허 요구사항 확인<br>시공능력평가액 조건 설정 |  |
| R_BUYER_TYPE_LOW_CONFIDENCE | validation | 기관유형 확인 필요 |  |  |  |  |  |  |  |  |  | source_mapping_required | 기관유형 확인 필요 | 정확한 발주기관 법적 성격 규명<br>적용 법체계 분기 |  |

## 금지 표현 정책
본 매핑 테이블의 어떠한 항목도 '계약 가능합니다', '구매 가능합니다', '지역제한 가능합니다', '수의계약 가능합니다', '낙찰 가능합니다'를 포함하지 않습니다.
