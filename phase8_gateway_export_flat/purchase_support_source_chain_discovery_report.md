# Phase 9.2-C Source Chain Discovery Report

## 1. Database Distributions
### Source Types
- `admrul_notice`: 137
- `admrul`: 35
- `law`: 24
- `admrul_instruction`: 9
- `admrul_regulation`: 5
- `skip_api`: 2
- `pdf_manual`: 2
- `law_decree`: 2
- `law_rule`: 1

### Law Categories
- `notice`: 130
- `regulation`: 23
- `admin_rule`: 23
- `enforcement_decree`: 14
- `act`: 11
- `instruction`: 9
- `enforcement_rule`: 5
- `ordinance`: 2

## 2. Mapping Summary
- **Total Rules**: 37
- **Mapped Verified**: 2
- **Mapped Candidate**: 2
- **Partial Mapped**: 27
- **Pending Resolution**: 2
- **Company API / Outside DB**: 4

## 3. Rule Source Mapping Details

### Category: `direct_contract`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_DIRECT_GENERAL_SMALL_AMOUNT` | 일반 소액수의계약 금액 기준 검토 | `partial_mapped` | 수의계약 | 국가계약법 시행령 제26조, 지방계약법 시행령 제25조 | Yes | 7 | 공정거래위원회 수의계약 운용지침 (Score: 75) |
| `R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY` | 일반 소액수의계약 우선 경로 배제 검토 | `partial_mapped` | 수의계약 | 국가계약법 시행령 제26조, 지방계약법 시행령 제25조 | Yes | 7 | 공정거래위원회 수의계약 운용지침 (Score: 75) |
| `R_DIRECT_ONE_PERSON_QUOTE` | 1인 견적 수의계약 사유 검토 | `partial_mapped` | 수의계약 | 1인 견적 | No | 7 | 공정거래위원회 수의계약 운용지침 (Score: 90) |
| `R_DIRECT_TWO_OR_MORE_QUOTES` | 2인 이상 견적 수의계약 절차 검토 | `partial_mapped` | 수의계약 | 2인 이상 견적 | No | 7 | 공정거래위원회 수의계약 운용지침 (Score: 90) |
| `R_DIRECT_POLICY_COMPANY` | 정책기업 특례 검토 | `mapped_verified` | 특례, 여성기업, 사회적기업, 장애인기업 | None | No | 12 | 여성기업지원에 관한 법률 (Score: 120) |
| `R_DIRECT_TECH_PRODUCT` | 기술개발제품·인증제품 특례 검토 | `partial_mapped` | 혁신제품, 기술개발제품, 우수조달 | 성능인증 | No | 3 | 혁신제품 구매 운영 규정 (Score: 110) |

### Category: `regional_restriction`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_REGIONAL_RESTRICTION_GOODS` | 물품 지역제한 경쟁입찰 검토 | `partial_mapped` | 물품 | 지방계약법 시행령, 국가계약법 시행령, 주된 영업소, 제한경쟁, 입찰참가자격 제한 | No | 14 | 물품 다수공급자계약 업무처리규정 (Score: 110) |
| `R_REGIONAL_RESTRICTION_SERVICE` | 용역 지역제한 경쟁입찰 검토 | `partial_mapped` | 용역 | 지방계약법 시행령, 국가계약법 시행령, 주된 영업소, 제한경쟁, 입찰참가자격 제한 | No | 19 | 국토지리정보원 용역사업 검사업무 규정 (Score: 80) |
| `R_REGIONAL_RESTRICTION_CONSTRUCTION` | 공사 지역제한 경쟁입찰 검토 | `partial_mapped` | 공사 | 지방계약법 시행령, 국가계약법 시행령, 주된 영업소, 제한경쟁, 입찰참가자격 제한 | No | 20 | 중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역 (Score: 110) |
| `R_LIMITED_COMPETITION_REVIEW` | 제한경쟁입찰 검토 | `pending_resolution` | None | 제한경쟁, 지방계약법 시행령, 국가계약법 시행령, 입찰참가자격 제한 | No | 0 | None |

### Category: `evaluation`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_EVALUATION_CRITERIA_REVIEW` | 적격심사·종합평가·기술평가 기준 확인 | `partial_mapped` | 종합평가, 적격심사, 낙찰자 결정기준 | 기술평가 | No | 25 | 지방자치단체 입찰시 낙찰자 결정기준 (Score: 100) |

### Category: `joint_contract`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_LOCAL_REGIONAL_JOINT_CONTRACT` | 지방계약 기준 지역의무공동도급 검토 | `partial_mapped` | 공동계약 | 지방계약법, 지역의무공동도급 | Yes | 2 | 공동계약운용요령 (Score: 90) |
| `R_NATIONAL_REGIONAL_JOINT_CONTRACT` | 국가계약 기준 지역의무공동도급 검토 | `partial_mapped` | 공동계약 | 국가계약법, 지역의무공동도급 | Yes | 2 | 공동계약운용요령 (Score: 90) |
| `R_PUBLIC_INSTITUTION_REGIONAL_JOINT_CONTRACT_CHECK` | 공공기관 내부규정상 지역공동도급 기준 확인 | `partial_mapped` | 공동계약, 공공기관 | 내부규정 | No | 14 | 공공기관의 운영에 관한 법률 (Score: 120) |
| `R_JOINT_CONTRACT_NOT_PRIMARY_GOODS` | 물품 지역의무공동도급 우선 경로 배제 | `mapped_candidate` | 공동계약, 물품구매 | None | No | 6 | 공동계약운용요령 (Score: 90) |
| `R_JOINT_CONTRACT_NOT_PRIMARY_SERVICE` | 일반용역 지역의무공동도급 우선 경로 배제 | `mapped_candidate` | 공동계약, 일반용역 | None | No | 5 | 공동계약운용요령 (Score: 90) |

### Category: `participation_points`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_GOODS_REGIONAL_POINTS_NOT_PRIMARY` | 물품 지역업체 가점 우선 경로 배제 | `partial_mapped` | 물품 | 지역업체 가점 | No | 14 | 물품 다수공급자계약 업무처리규정 (Score: 110) |
| `R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK` | 용역 평가기준상 지역업체 참여도·가점 확인 | `partial_mapped` | 제안서평가, 적격심사 | 지역업체 참여도 | No | 25 | 물품 적격심사기준에 관한 훈령 (Score: 80) |
| `R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK` | 공사 적격심사·종합평가·기술평가상 지역업체 참여도 확인 | `partial_mapped` | 적격심사 | 지역업체 배점 | No | 21 | 물품 적격심사기준에 관한 훈령 (Score: 80) |
| `R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW` | MAS 2단계경쟁 지역업체 평가항목 검토 | `partial_mapped` | 2단계경쟁, 다수공급자계약 | 지역업체, 다수공급자계약 | Yes | 2 | 물품 다수공급자계약 업무처리규정 (Score: 110) |

### Category: `local_priority`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_LOCAL_PRODUCT_PRIORITY` | 지역상품 우선구매 조례·시책 검토 | `partial_mapped` | 우선구매 | 지역상품, 조례 | No | 1 | 중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙 (Score: 110) |

### Category: `policy_company`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_POLICY_COMPANY_PREFERENCE` | 정책기업 우대·우선구매 검토 | `mapped_verified` | 장애인기업, 여성기업, 사회적기업, 우선구매 | None | No | 7 | 여성기업지원에 관한 법률 (Score: 120) |
| `R_SOCIAL_VALUE_PURCHASE_REVIEW` | 사회적경제기업·중증장애인생산품 등 우선구매 검토 | `partial_mapped` | 우선구매 | 사회적경제기업, 사회적가치, 장애인생산품, 중증장애인생산품 | No | 1 | 중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙 (Score: 110) |

### Category: `shopping_mall`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_SHOPPING_MALL_ROUTE_CLASSIFICATION` | 종합쇼핑몰 등록 물품 경로 구분 | `partial_mapped` | 종합쇼핑몰, MAS | 제3자단가계약 | No | 2 | 국가종합전자조달시스템 종합쇼핑몰 운영규정 (Score: 110) |
| `R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW` | 제3자단가계약 직접 납품요구 검토 | `pending_resolution` | None | 조달사업법 시행령, 제3자를 위한 단가계약, 납품요구, 제3자단가계약 | No | 0 | None |
| `R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT` | MAS 일반제품 2단계경쟁 기준 검토 | `partial_mapped` | 다수공급자계약 | 일반제품, 기준금액 | Yes | 2 | 물품 다수공급자계약 업무처리규정 (Score: 120) |
| `R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION` | MAS 중소기업자간 경쟁제품 2단계경쟁 기준 검토 | `partial_mapped` | 중소기업자간 경쟁제품, 다수공급자계약 | 기준금액 | Yes | 3 | 물품 다수공급자계약 업무처리규정 (Score: 120) |
| `R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL` | 중소기업 제조품목 선택 적용 구간 검토 | `partial_mapped` | 다수공급자계약 | 중소기업 제조품목 | Yes | 2 | 물품 다수공급자계약 업무처리규정 (Score: 120) |
| `R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW` | 2단계경쟁 대상 금액 미만 지역업체 후보 조회 | `partial_mapped` | 다수공급자계약 | 직접 납품요구, 2단계경쟁 예외 | No | 2 | 물품 다수공급자계약 업무처리규정 (Score: 120) |
| `R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW` | MAS 2단계경쟁 종합평가·표준평가 방식 검토 | `partial_mapped` | 다수공급자계약 | 표준평가방식, 다수공급자계약 | No | 2 | 물품 다수공급자계약 업무처리규정 (Score: 120) |
| `R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP` | MAS·종합쇼핑몰 내 지역업체 후보 조회 | `company_api_mapping_required` | 종합쇼핑몰 | 지역업체 등록현황 | No | 1 | 국가종합전자조달시스템 종합쇼핑몰 운영규정 (Score: 110) |

### Category: `item_eligibility`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_EXPLICIT_ITEM_ELIGIBILITY` | 중기경쟁제품·직접생산확인 추가 검토 | `partial_mapped` | 중소기업자간 경쟁제품 | 직접생산확인증명서 | No | 1 | 중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역 (Score: 110) |
| `R_TECH_DEVELOPMENT_PRODUCT_REVIEW` | 기술개발제품·성능인증·혁신제품 확인 | `partial_mapped` | 혁신제품, 기술개발제품 | 성능인증 | No | 2 | 혁신제품 구매 운영 규정 (Score: 110) |

### Category: `candidate_lookup`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_COMPANY_CANDIDATE_LOOKUP_GOODS` | 물품 후보업체 조회 | `company_api_mapping_required` | None | None | No | 0 | None |
| `R_COMPANY_CANDIDATE_LOOKUP_SERVICE` | 용역 후보업체 조회 | `company_api_mapping_required` | None | None | No | 0 | None |
| `R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION` | 공사 면허업체 후보 조회 | `company_api_mapping_required` | None | None | No | 0 | None |

### Category: `validation`

| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |
|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|
| `R_BUYER_TYPE_LOW_CONFIDENCE` | 기관유형 확인 필요 | `partial_mapped` | 지방계약, 국가계약 | 공공기관운영법 | No | 3 | 지방계약 전문기관 지정 (Score: 80) |

