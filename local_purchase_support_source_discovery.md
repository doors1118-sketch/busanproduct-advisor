# Phase 9.2 Evidence-Based Source Discovery

본 문서는 Rule Catalog v0.2의 각 항목에 대한 법적 근거 매핑(Source Chain Mapping) 명세입니다.

## R_DIRECT_GENERAL_SMALL_AMOUNT: 일반 소액수의계약 금액 기준 검토
- **관련 법령·시행령·기준**: 소액수의계약, 지방계약법 시행령 제25조, 국가계약법 시행령 제26조
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음
- **견적 방식**: direct_contract_general
- **숫자/비율 파라미터**: P_GENERAL_SMALL_DIRECT_CONTRACT_THRESHOLD (매핑 필요)

## R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY: 일반 소액수의계약 우선 경로 배제 검토
- **관련 법령·시행령·기준**: 소액수의계약, 금액 초과
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: not_primary_route
- **금액 기준**: type=exceeds_general_small_direct_threshold, min=, max=
- **숫자/비율 파라미터**: P_GENERAL_SMALL_DIRECT_CONTRACT_THRESHOLD (매핑 필요)

## R_DIRECT_ONE_PERSON_QUOTE: 1인 견적 수의계약 사유 검토
- **관련 법령·시행령·기준**: 1인 견적, 수의계약
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음
- **견적 방식**: one_person_quote

## R_DIRECT_TWO_OR_MORE_QUOTES: 2인 이상 견적 수의계약 절차 검토
- **관련 법령·시행령·기준**: 2인 이상 견적, 수의계약
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음
- **견적 방식**: two_or_more_quotes

## R_DIRECT_POLICY_COMPANY: 정책기업 특례 검토
- **관련 법령·시행령·기준**: 여성기업, 장애인기업, 사회적기업, 특례
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: type=policy_company_check_relevant, min=, max=

## R_DIRECT_TECH_PRODUCT: 기술개발제품·인증제품 특례 검토
- **관련 법령·시행령·기준**: 우수조달, 혁신제품, 성능인증, 기술개발제품
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: type=product_certification_check_relevant, min=, max=

## R_REGIONAL_RESTRICTION_GOODS: 물품 지역제한 경쟁입찰 검토
- **관련 법령·시행령·기준**: 지역제한, 제한경쟁, 주된 영업소
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_REGIONAL_RESTRICTION_SERVICE: 용역 지역제한 경쟁입찰 검토
- **관련 법령·시행령·기준**: 지역제한, 제한경쟁, 주된 영업소
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_REGIONAL_RESTRICTION_CONSTRUCTION: 공사 지역제한 경쟁입찰 검토
- **관련 법령·시행령·기준**: 지역제한, 제한경쟁, 주된 영업소
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_LIMITED_COMPETITION_REVIEW: 제한경쟁입찰 검토
- **관련 법령·시행령·기준**: 제한경쟁, 참가자격 제한
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_EVALUATION_CRITERIA_REVIEW: 적격심사·종합평가·기술평가 기준 확인
- **관련 법령·시행령·기준**: 적격심사, 종합평가, 기술평가, 낙찰자 결정기준
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_LOCAL_REGIONAL_JOINT_CONTRACT: 지방계약 기준 지역의무공동도급 검토
- **관련 법령·시행령·기준**: 지역의무공동도급, 지방계약법, 공동계약
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음
- **숫자/비율 파라미터**: P_LOCAL_JOINT_CONTRACT_MIN_SHARE, P_LOCAL_JOINT_CONTRACT_MAX_SHARE (매핑 필요)

## R_NATIONAL_REGIONAL_JOINT_CONTRACT: 국가계약 기준 지역의무공동도급 검토
- **관련 법령·시행령·기준**: 지역의무공동도급, 국가계약법, 공동계약
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음
- **숫자/비율 파라미터**: P_NATIONAL_JOINT_CONTRACT_MIN_SHARE (매핑 필요)

## R_PUBLIC_INSTITUTION_REGIONAL_JOINT_CONTRACT_CHECK: 공공기관 내부규정상 지역공동도급 기준 확인
- **관련 법령·시행령·기준**: 공공기관, 내부규정, 공동계약
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_JOINT_CONTRACT_NOT_PRIMARY_GOODS: 물품 지역의무공동도급 우선 경로 배제
- **관련 법령·시행령·기준**: 공동계약, 물품구매
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: not_primary_route
- **금액 기준**: 없음

## R_JOINT_CONTRACT_NOT_PRIMARY_SERVICE: 일반용역 지역의무공동도급 우선 경로 배제
- **관련 법령·시행령·기준**: 공동계약, 일반용역
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: not_primary_route
- **금액 기준**: 없음

## R_GOODS_REGIONAL_POINTS_NOT_PRIMARY: 물품 지역업체 가점 우선 경로 배제
- **관련 법령·시행령·기준**: 물품, 지역업체 가점
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: not_primary_route
- **금액 기준**: 없음

## R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK: 용역 평가기준상 지역업체 참여도·가점 확인
- **관련 법령·시행령·기준**: 적격심사, 제안서평가, 지역업체 참여도
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK: 공사 적격심사·종합평가·기술평가상 지역업체 참여도 확인
- **관련 법령·시행령·기준**: 적격심사, 지역업체 배점
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW: MAS 2단계경쟁 지역업체 평가항목 검토
- **관련 법령·시행령·기준**: 다수공급자계약, 2단계경쟁, 종합평가방식, 지역업체
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: evaluation_criteria_check_required
- **금액 기준**: 없음
- **숫자/비율 파라미터**: P_MAS_SECOND_STAGE_MAX_SCORE (매핑 필요)
- **가점·배점 기준**: 최대 7.5 점 (다수공급자계약 2단계경쟁 종합평가방식 선택 평가항목)

## R_LOCAL_PRODUCT_PRIORITY: 지역상품 우선구매 조례·시책 검토
- **관련 법령·시행령·기준**: 우선구매, 조례, 지역상품
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_POLICY_COMPANY_PREFERENCE: 정책기업 우대·우선구매 검토
- **관련 법령·시행령·기준**: 여성기업, 사회적기업, 장애인기업, 우선구매
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_SOCIAL_VALUE_PURCHASE_REVIEW: 사회적경제기업·중증장애인생산품 등 우선구매 검토
- **관련 법령·시행령·기준**: 사회적가치, 중증장애인생산품
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_SHOPPING_MALL_ROUTE_CLASSIFICATION: 종합쇼핑몰 등록 물품 경로 구분
- **관련 법령·시행령·기준**: 종합쇼핑몰, MAS, 제3자단가계약
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW: 제3자단가계약 직접 납품요구 검토
- **관련 법령·시행령·기준**: 제3자를 위한 단가계약, 직접 납품요구
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT: MAS 일반제품 2단계경쟁 기준 검토
- **관련 법령·시행령·기준**: 다수공급자계약, 일반제품, 기준금액
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음
- **숫자/비율 파라미터**: P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD (매핑 필요)

## R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION: MAS 중소기업자간 경쟁제품 2단계경쟁 기준 검토
- **관련 법령·시행령·기준**: 다수공급자계약, 중소기업자간 경쟁제품, 기준금액
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음
- **숫자/비율 파라미터**: P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD (매핑 필요)

## R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL: 중소기업 제조품목 선택 적용 구간 검토
- **관련 법령·시행령·기준**: 다수공급자계약, 중소기업 제조품목
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음
- **숫자/비율 파라미터**: P_MAS_SECOND_STAGE_SME_MANUFACTURED_OPTIONAL_MIN, P_MAS_SECOND_STAGE_SME_MANUFACTURED_OPTIONAL_MAX (매핑 필요)

## R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW: 2단계경쟁 대상 금액 미만 지역업체 후보 조회
- **관련 법령·시행령·기준**: 다수공급자계약, 2단계경쟁 예외, 직접 납품요구
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: type=below_second_stage_threshold, min=, max=

## R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW: MAS 2단계경쟁 종합평가·표준평가 방식 검토
- **관련 법령·시행령·기준**: 다수공급자계약, 종합평가방식, 표준평가방식
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP: MAS·종합쇼핑몰 내 지역업체 후보 조회
- **관련 법령·시행령·기준**: 종합쇼핑몰, 지역업체 등록현황
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_EXPLICIT_ITEM_ELIGIBILITY: 중기경쟁제품·직접생산확인 추가 검토
- **관련 법령·시행령·기준**: 중소기업자간 경쟁제품, 직접생산확인증명서
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_TECH_DEVELOPMENT_PRODUCT_REVIEW: 기술개발제품·성능인증·혁신제품 확인
- **관련 법령·시행령·기준**: 기술개발제품, 혁신제품, 성능인증
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_COMPANY_CANDIDATE_LOOKUP_GOODS: 물품 후보업체 조회
- **관련 법령·시행령·기준**: 
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_COMPANY_CANDIDATE_LOOKUP_SERVICE: 용역 후보업체 조회
- **관련 법령·시행령·기준**: 
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION: 공사 면허업체 후보 조회
- **관련 법령·시행령·기준**: 
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

## R_BUYER_TYPE_LOW_CONFIDENCE: 기관유형 확인 필요
- **관련 법령·시행령·기준**: 국가계약, 지방계약, 공공기관운영법
- **DB source_id 후보**: 미정
- **source_id 확정 여부**: source_mapping_required
- **금액 기준**: 없음

