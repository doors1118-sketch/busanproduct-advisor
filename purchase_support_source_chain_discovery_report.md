# Phase 9.2-B Source Chain Discovery Report

## 1. Mapping Summary
- **Total Rules**: 37
- **Resolved**: 4
- **Partial Mapped**: 21
- **Pending Resolution**: 8
- **Company API / Outside DB**: 4

## 2. Rule Source Mapping Details

### Category: `direct_contract`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_DIRECT_GENERAL_SMALL_AMOUNT` | 일반 소액수의계약 금액 기준 검토 | `pending_resolution` | 0 found | 지방계약법 시행령 제25조, 국가계약법 시행령 제26조, 소액수의계약 | P_GENERAL_SMALL_DIRECT_CONTRACT_THRESHOLD |
| `R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY` | 일반 소액수의계약 우선 경로 배제 검토 | `pending_resolution` | 0 found | 금액 초과, 소액수의계약 | P_GENERAL_SMALL_DIRECT_CONTRACT_THRESHOLD |
| `R_DIRECT_ONE_PERSON_QUOTE` | 1인 견적 수의계약 사유 검토 | `partial_mapped` | 7 found | 1인 견적 | None |
| `R_DIRECT_TWO_OR_MORE_QUOTES` | 2인 이상 견적 수의계약 절차 검토 | `partial_mapped` | 7 found | 2인 이상 견적 | None |
| `R_DIRECT_POLICY_COMPANY` | 정책기업 특례 검토 | `resolved` | 12 found | None | None |
| `R_DIRECT_TECH_PRODUCT` | 기술개발제품·인증제품 특례 검토 | `partial_mapped` | 3 found | 성능인증 | None |

### Category: `regional_restriction`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_REGIONAL_RESTRICTION_GOODS` | 물품 지역제한 경쟁입찰 검토 | `pending_resolution` | 0 found | 지역제한, 제한경쟁, 주된 영업소 | None |
| `R_REGIONAL_RESTRICTION_SERVICE` | 용역 지역제한 경쟁입찰 검토 | `pending_resolution` | 0 found | 지역제한, 제한경쟁, 주된 영업소 | None |
| `R_REGIONAL_RESTRICTION_CONSTRUCTION` | 공사 지역제한 경쟁입찰 검토 | `pending_resolution` | 0 found | 지역제한, 제한경쟁, 주된 영업소 | None |
| `R_LIMITED_COMPETITION_REVIEW` | 제한경쟁입찰 검토 | `pending_resolution` | 0 found | 참가자격 제한, 제한경쟁 | None |

### Category: `evaluation`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_EVALUATION_CRITERIA_REVIEW` | 적격심사·종합평가·기술평가 기준 확인 | `partial_mapped` | 25 found | 기술평가 | None |

### Category: `joint_contract`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_LOCAL_REGIONAL_JOINT_CONTRACT` | 지방계약 기준 지역의무공동도급 검토 | `partial_mapped` | 2 found | 지역의무공동도급, 지방계약법 | P_LOCAL_JOINT_CONTRACT_MIN_SHARE, P_LOCAL_JOINT_CONTRACT_MAX_SHARE |
| `R_NATIONAL_REGIONAL_JOINT_CONTRACT` | 국가계약 기준 지역의무공동도급 검토 | `partial_mapped` | 2 found | 국가계약법, 지역의무공동도급 | P_NATIONAL_JOINT_CONTRACT_MIN_SHARE |
| `R_PUBLIC_INSTITUTION_REGIONAL_JOINT_CONTRACT_CHECK` | 공공기관 내부규정상 지역공동도급 기준 확인 | `partial_mapped` | 14 found | 내부규정 | None |
| `R_JOINT_CONTRACT_NOT_PRIMARY_GOODS` | 물품 지역의무공동도급 우선 경로 배제 | `resolved` | 6 found | None | None |
| `R_JOINT_CONTRACT_NOT_PRIMARY_SERVICE` | 일반용역 지역의무공동도급 우선 경로 배제 | `resolved` | 5 found | None | None |

### Category: `participation_points`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_GOODS_REGIONAL_POINTS_NOT_PRIMARY` | 물품 지역업체 가점 우선 경로 배제 | `partial_mapped` | 14 found | 지역업체 가점 | None |
| `R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK` | 용역 평가기준상 지역업체 참여도·가점 확인 | `partial_mapped` | 25 found | 지역업체 참여도 | None |
| `R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK` | 공사 적격심사·종합평가·기술평가상 지역업체 참여도 확인 | `partial_mapped` | 21 found | 지역업체 배점 | None |
| `R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW` | MAS 2단계경쟁 지역업체 평가항목 검토 | `partial_mapped` | 2 found | 종합평가방식, 지역업체 | P_MAS_SECOND_STAGE_MAX_SCORE |

### Category: `local_priority`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_LOCAL_PRODUCT_PRIORITY` | 지역상품 우선구매 조례·시책 검토 | `partial_mapped` | 1 found | 조례, 지역상품 | None |

### Category: `policy_company`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_POLICY_COMPANY_PREFERENCE` | 정책기업 우대·우선구매 검토 | `resolved` | 7 found | None | None |
| `R_SOCIAL_VALUE_PURCHASE_REVIEW` | 사회적경제기업·중증장애인생산품 등 우선구매 검토 | `pending_resolution` | 0 found | 사회적가치, 중증장애인생산품 | None |

### Category: `shopping_mall`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_SHOPPING_MALL_ROUTE_CLASSIFICATION` | 종합쇼핑몰 등록 물품 경로 구분 | `partial_mapped` | 1 found | 제3자단가계약, MAS | None |
| `R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW` | 제3자단가계약 직접 납품요구 검토 | `pending_resolution` | 0 found | 제3자를 위한 단가계약, 직접 납품요구 | None |
| `R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT` | MAS 일반제품 2단계경쟁 기준 검토 | `partial_mapped` | 2 found | 기준금액, 일반제품 | P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD |
| `R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION` | MAS 중소기업자간 경쟁제품 2단계경쟁 기준 검토 | `partial_mapped` | 3 found | 기준금액 | P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD |
| `R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL` | 중소기업 제조품목 선택 적용 구간 검토 | `partial_mapped` | 2 found | 중소기업 제조품목 | P_MAS_SECOND_STAGE_SME_MANUFACTURED_OPTIONAL_MIN, P_MAS_SECOND_STAGE_SME_MANUFACTURED_OPTIONAL_MAX |
| `R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW` | 2단계경쟁 대상 금액 미만 지역업체 후보 조회 | `partial_mapped` | 2 found | 2단계경쟁 예외, 직접 납품요구 | None |
| `R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW` | MAS 2단계경쟁 종합평가·표준평가 방식 검토 | `partial_mapped` | 2 found | 표준평가방식, 종합평가방식 | None |
| `R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP` | MAS·종합쇼핑몰 내 지역업체 후보 조회 | `company_api_mapping_required` | 1 found | 지역업체 등록현황 | None |

### Category: `item_eligibility`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_EXPLICIT_ITEM_ELIGIBILITY` | 중기경쟁제품·직접생산확인 추가 검토 | `partial_mapped` | 1 found | 직접생산확인증명서 | None |
| `R_TECH_DEVELOPMENT_PRODUCT_REVIEW` | 기술개발제품·성능인증·혁신제품 확인 | `partial_mapped` | 2 found | 성능인증 | None |

### Category: `candidate_lookup`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_COMPANY_CANDIDATE_LOOKUP_GOODS` | 물품 후보업체 조회 | `company_api_mapping_required` | 0 found | None | None |
| `R_COMPANY_CANDIDATE_LOOKUP_SERVICE` | 용역 후보업체 조회 | `company_api_mapping_required` | 0 found | None | None |
| `R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION` | 공사 면허업체 후보 조회 | `company_api_mapping_required` | 0 found | None | None |

### Category: `validation`

| Rule ID | Name | Status | Primary Sources | Unmatched Terms | Numeric Params |
|---------|------|--------|-----------------|-----------------|----------------|
| `R_BUYER_TYPE_LOW_CONFIDENCE` | 기관유형 확인 필요 | `partial_mapped` | 3 found | 공공기관운영법 | None |

