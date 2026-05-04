# Phase 9.2-B Source Chain Discovery Report

## 1. Mapping Summary
- **Total Rules**: 37
- **Mapped Verified**: 2
- **Mapped Candidate**: 4
- **Partial Mapped**: 19
- **Pending Resolution**: 8
- **Company API / Outside DB**: 4

## 2. Rule Source Mapping Details

### Category: `direct_contract`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_DIRECT_GENERAL_SMALL_AMOUNT` | 일반 소액수의계약 금액 기준 검토 | `pending_resolution` | 0 / 0 | None | 국가계약법 시행령 제26조, 소액수의계약, 지방계약법 시행령 제25조 | Yes |
| `R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY` | 일반 소액수의계약 우선 경로 배제 검토 | `pending_resolution` | 0 / 0 | None | 금액 초과, 소액수의계약 | Yes |
| `R_DIRECT_ONE_PERSON_QUOTE` | 1인 견적 수의계약 사유 검토 | `mapped_candidate` | 0 / 7 | 공정거래위원회 수의계약 운용지침<br>국가인권위원회 수의계약 운용ㆍ집행 지침<br>보훈ㆍ복지단체 수의계약업무 처리지침<br>경쟁촉진을 위한 공사의 수의계약사유 평가기준<br>조달청 군수품 보훈ㆍ복지단체 수의계약업무 처리지침<br>공공기관이 자회사 등과 수의계약을 할 수 있는 고용 기준에 관한 고시<br>지방자치단체를 당사자로 하는 계약에 관한 법률 시행령의 수의계약 등 한시적 특례 적용기간에 관한 고시 | None | No |
| `R_DIRECT_TWO_OR_MORE_QUOTES` | 2인 이상 견적 수의계약 절차 검토 | `mapped_candidate` | 0 / 7 | 공정거래위원회 수의계약 운용지침<br>국가인권위원회 수의계약 운용ㆍ집행 지침<br>보훈ㆍ복지단체 수의계약업무 처리지침<br>경쟁촉진을 위한 공사의 수의계약사유 평가기준<br>조달청 군수품 보훈ㆍ복지단체 수의계약업무 처리지침<br>공공기관이 자회사 등과 수의계약을 할 수 있는 고용 기준에 관한 고시<br>지방자치단체를 당사자로 하는 계약에 관한 법률 시행령의 수의계약 등 한시적 특례 적용기간에 관한 고시 | None | No |
| `R_DIRECT_POLICY_COMPANY` | 정책기업 특례 검토 | `mapped_verified` | 6 / 6 | 여성기업지원에 관한 법률<br>여성기업지원에 관한 법률 시행령<br>장애인기업활동 촉진법<br>장애인기업활동 촉진법 시행령<br>사회적기업 육성법<br>사회적기업 육성법 시행령<br>국가계약 시범특례 운영 지침<br>특정물품등의조달에관한국가를당사자로하는계약에관한법률시행령특례규정<br>특정물품등의조달에관한국가를당사자로하는계약에관한법률시행특례규칙<br>특정조달을 위한 국가를 당사자로 하는 계약에 관한 법률 시행령 특례규정<br>특정조달을 위한 국가를 당사자로 하는 계약에 관한 법률 시행 특례규칙<br>지방자치단체를 당사자로 하는 계약에 관한 법률 시행령의 수의계약 등 한시적 특례 적용기간에 관한 고시 | None | No |
| `R_DIRECT_TECH_PRODUCT` | 기술개발제품·인증제품 특례 검토 | `partial_mapped` | 3 / 0 | 우수조달물품 지정ㆍ관리 규정<br>혁신제품 구매 운영 규정<br>중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙 | 성능인증 | No |

### Category: `regional_restriction`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_REGIONAL_RESTRICTION_GOODS` | 물품 지역제한 경쟁입찰 검토 | `pending_resolution` | 0 / 0 | None | 제한경쟁, 지역제한, 주된 영업소 | No |
| `R_REGIONAL_RESTRICTION_SERVICE` | 용역 지역제한 경쟁입찰 검토 | `pending_resolution` | 0 / 0 | None | 제한경쟁, 지역제한, 주된 영업소 | No |
| `R_REGIONAL_RESTRICTION_CONSTRUCTION` | 공사 지역제한 경쟁입찰 검토 | `pending_resolution` | 0 / 0 | None | 제한경쟁, 지역제한, 주된 영업소 | No |
| `R_LIMITED_COMPETITION_REVIEW` | 제한경쟁입찰 검토 | `pending_resolution` | 0 / 0 | None | 제한경쟁, 참가자격 제한 | No |

### Category: `evaluation`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_EVALUATION_CRITERIA_REVIEW` | 적격심사·종합평가·기술평가 기준 확인 | `partial_mapped` | 1 / 24 | 물품 적격심사기준에 관한 훈령<br>일반용역 적격심사기준에 관한 훈령<br>건설엔지니어링 적격심사 및 협상에 의한 낙찰자 결정기준<br>군시설공사 적격심사기준에 관한 훈령<br>기술용역 적격심사 및 협상에 의한 낙찰자 결정기준<br>기술용역 적격심사기준에 관한 훈령<br>기술용역적격심사 세부기준<br>조달청 공공주택 적격심사세부기준<br>국외조달 적격심사 기준<br>국제운송 적격심사 기준<br>산림청 산림사업 적격심사 세부기준<br>우편기계 유지보수 위탁용역에 관한 적격심사 지침<br>일반용역적격심사 세부기준<br>장비정비용역 적격심사 기준<br>전투근무지원정 적격심사 기준<br>매장유산 조사용역 적격심사 세부기준<br>조달청 일반용역 적격심사 세부기준<br>조달청 군수품 구매 적격심사 세부기준<br>조달청 기술용역 적격심사 세부기준<br>조달청 물품구매적격심사 세부기준<br>조달청 시설공사 적격심사세부기준<br>2017년도 「문화재수리 종합평가 낙찰자 결정기준」 적용대상 문화재수리(추가)<br>국가유산수리 종합심사(종합평가) 적용대상 국가유산수리<br>지방자치단체 입찰시 낙찰자 결정기준<br>일괄입찰 등에 의한 낙찰자 결정기준 | 기술평가 | No |

### Category: `joint_contract`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_LOCAL_REGIONAL_JOINT_CONTRACT` | 지방계약 기준 지역의무공동도급 검토 | `partial_mapped` | 0 / 2 | 공동계약운용요령<br>국가를 당사자로 하는 계약에 관한 법률 시행령 제72조제3항제2호에 따른 공동계약 대상사업 | 지방계약법, 지역의무공동도급 | Yes |
| `R_NATIONAL_REGIONAL_JOINT_CONTRACT` | 국가계약 기준 지역의무공동도급 검토 | `partial_mapped` | 0 / 2 | 공동계약운용요령<br>국가를 당사자로 하는 계약에 관한 법률 시행령 제72조제3항제2호에 따른 공동계약 대상사업 | 국가계약법, 지역의무공동도급 | Yes |
| `R_PUBLIC_INSTITUTION_REGIONAL_JOINT_CONTRACT_CHECK` | 공공기관 내부규정상 지역공동도급 기준 확인 | `partial_mapped` | 2 / 12 | 공공기관의 운영에 관한 법률<br>공공기관의 운영에 관한 법률 시행령<br>공공기관의 회계감사 및 결산감사에 관한 규칙<br>공공기관의 개발선정품 지정 및 운영에 관한 기준<br>공공기관이 자회사 등과 수의계약을 할 수 있는 고용 기준에 관한 고시<br>공공기관 구매위탁 예외에 관한 처리지침<br>기타공공기관 계약사무 운영규정<br>문화체육관광부 소관 기타공공기관 등의 경영평가에 관한 규정<br>2020년 공공기관 지정 고시<br>공공기관 구분회계 운영 지침<br>한국보건복지정보개발원 공공기관 변경지정<br>한국청소년활동진흥원 공공기관 변경지정<br>공동계약운용요령<br>국가를 당사자로 하는 계약에 관한 법률 시행령 제72조제3항제2호에 따른 공동계약 대상사업 | 내부규정 | No |
| `R_JOINT_CONTRACT_NOT_PRIMARY_GOODS` | 물품 지역의무공동도급 우선 경로 배제 | `mapped_candidate` | 0 / 6 | 공동계약운용요령<br>국가를 당사자로 하는 계약에 관한 법률 시행령 제72조제3항제2호에 따른 공동계약 대상사업<br>물품구매(제조)계약일반조건<br>물품구매(제조)입찰유의서<br>조달청 물품구매적격심사 세부기준<br>물품구매계약 품질관리 특수조건 | None | No |
| `R_JOINT_CONTRACT_NOT_PRIMARY_SERVICE` | 일반용역 지역의무공동도급 우선 경로 배제 | `mapped_candidate` | 0 / 5 | 공동계약운용요령<br>국가를 당사자로 하는 계약에 관한 법률 시행령 제72조제3항제2호에 따른 공동계약 대상사업<br>일반용역 적격심사기준에 관한 훈령<br>일반용역적격심사 세부기준<br>조달청 일반용역 적격심사 세부기준 | None | No |

### Category: `participation_points`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_GOODS_REGIONAL_POINTS_NOT_PRIMARY` | 물품 지역업체 가점 우선 경로 배제 | `partial_mapped` | 3 / 11 | 물품 다수공급자계약 업무처리규정<br>조달청 제조물품 직접생산확인 기준<br>우수조달물품 지정ㆍ관리 규정<br>물품구매(제조)계약일반조건<br>물품 적격심사기준에 관한 훈령<br>물품구매(제조)입찰유의서<br>품질보증조달물품 지정 및 관리규정<br>조달청 물품구매적격심사 세부기준<br>특정물품등의조달에관한국가를당사자로하는계약에관한법률시행령특례규정<br>특정물품등의조달에관한국가를당사자로하는계약에관한법률시행특례규칙<br>국제입찰에 의하는 지방자치단체의 공사 및 물품ㆍ용역의 범위에 관한 고시<br>수요기관 자체조달 물품ㆍ용역에 대한 납품검사 대행 기준<br>물품구매계약 품질관리 특수조건<br>지방자치단체를 당사자로 하는 계약에 관한 법률 시행령 제6조의2 및 공유재산 및 물품 관리법 시행령 제13조, 제26조, 제78조에 따른 정보처리장치의 지정에 관한 고시 | 지역업체 가점 | No |
| `R_SERVICE_REGIONAL_POINTS_EVALUATION_CHECK` | 용역 평가기준상 지역업체 참여도·가점 확인 | `partial_mapped` | 0 / 25 | 물품 적격심사기준에 관한 훈령<br>일반용역 적격심사기준에 관한 훈령<br>건설엔지니어링 적격심사 및 협상에 의한 낙찰자 결정기준<br>군시설공사 적격심사기준에 관한 훈령<br>기술용역 적격심사 및 협상에 의한 낙찰자 결정기준<br>기술용역 적격심사기준에 관한 훈령<br>기술용역적격심사 세부기준<br>조달청 공공주택 적격심사세부기준<br>국외조달 적격심사 기준<br>국제운송 적격심사 기준<br>산림청 산림사업 적격심사 세부기준<br>우편기계 유지보수 위탁용역에 관한 적격심사 지침<br>일반용역적격심사 세부기준<br>장비정비용역 적격심사 기준<br>전투근무지원정 적격심사 기준<br>매장유산 조사용역 적격심사 세부기준<br>조달청 일반용역 적격심사 세부기준<br>조달청 군수품 구매 적격심사 세부기준<br>조달청 기술용역 적격심사 세부기준<br>조달청 물품구매적격심사 세부기준<br>조달청 시설공사 적격심사세부기준<br>통일부 협상에 의한 계약 제안서평가 업무처리 규정<br>새만금개발청 협상에 의한 계약 제안서평가 세부기준<br>협상에 의한 계약 및 제안서평가 세부기준<br>조달청 협상에 의한 계약 제안서평가 세부기준 | 지역업체 참여도 | No |
| `R_CONSTRUCTION_REGIONAL_POINTS_QUALIFICATION_CHECK` | 공사 적격심사·종합평가·기술평가상 지역업체 참여도 확인 | `partial_mapped` | 0 / 21 | 물품 적격심사기준에 관한 훈령<br>일반용역 적격심사기준에 관한 훈령<br>건설엔지니어링 적격심사 및 협상에 의한 낙찰자 결정기준<br>군시설공사 적격심사기준에 관한 훈령<br>기술용역 적격심사 및 협상에 의한 낙찰자 결정기준<br>기술용역 적격심사기준에 관한 훈령<br>기술용역적격심사 세부기준<br>조달청 공공주택 적격심사세부기준<br>국외조달 적격심사 기준<br>국제운송 적격심사 기준<br>산림청 산림사업 적격심사 세부기준<br>우편기계 유지보수 위탁용역에 관한 적격심사 지침<br>일반용역적격심사 세부기준<br>장비정비용역 적격심사 기준<br>전투근무지원정 적격심사 기준<br>매장유산 조사용역 적격심사 세부기준<br>조달청 일반용역 적격심사 세부기준<br>조달청 군수품 구매 적격심사 세부기준<br>조달청 기술용역 적격심사 세부기준<br>조달청 물품구매적격심사 세부기준<br>조달청 시설공사 적격심사세부기준 | 지역업체 배점 | No |
| `R_MAS_SECOND_STAGE_REGIONAL_EVALUATION_REVIEW` | MAS 2단계경쟁 지역업체 평가항목 검토 | `partial_mapped` | 1 / 1 | 물품 다수공급자계약 업무처리규정<br>낙동강유역환경청 레미콘ㆍ아스콘 다수공급자계약 2단계경쟁 업무처리기준 | 지역업체 | Yes |

### Category: `local_priority`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_LOCAL_PRODUCT_PRIORITY` | 지역상품 우선구매 조례·시책 검토 | `partial_mapped` | 1 / 0 | 중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙 | 조례, 지역상품 | No |

### Category: `policy_company`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_POLICY_COMPANY_PREFERENCE` | 정책기업 우대·우선구매 검토 | `mapped_verified` | 7 / 0 | 여성기업지원에 관한 법률<br>여성기업지원에 관한 법률 시행령<br>사회적기업 육성법<br>사회적기업 육성법 시행령<br>장애인기업활동 촉진법<br>장애인기업활동 촉진법 시행령<br>중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙 | None | No |
| `R_SOCIAL_VALUE_PURCHASE_REVIEW` | 사회적경제기업·중증장애인생산품 등 우선구매 검토 | `pending_resolution` | 0 / 0 | None | 사회적가치, 중증장애인생산품 | No |

### Category: `shopping_mall`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_SHOPPING_MALL_ROUTE_CLASSIFICATION` | 종합쇼핑몰 등록 물품 경로 구분 | `partial_mapped` | 1 / 0 | 국가종합전자조달시스템 종합쇼핑몰 운영규정 | 제3자단가계약, MAS | No |
| `R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW` | 제3자단가계약 직접 납품요구 검토 | `pending_resolution` | 0 / 0 | None | 직접 납품요구, 제3자를 위한 단가계약 | No |
| `R_MAS_SECOND_STAGE_THRESHOLD_GENERAL_PRODUCT` | MAS 일반제품 2단계경쟁 기준 검토 | `partial_mapped` | 1 / 1 | 물품 다수공급자계약 업무처리규정<br>낙동강유역환경청 레미콘ㆍ아스콘 다수공급자계약 2단계경쟁 업무처리기준 | 일반제품, 기준금액 | Yes |
| `R_MAS_SECOND_STAGE_THRESHOLD_SME_COMPETITION` | MAS 중소기업자간 경쟁제품 2단계경쟁 기준 검토 | `partial_mapped` | 2 / 1 | 물품 다수공급자계약 업무처리규정<br>낙동강유역환경청 레미콘ㆍ아스콘 다수공급자계약 2단계경쟁 업무처리기준<br>중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역 | 기준금액 | Yes |
| `R_MAS_SECOND_STAGE_THRESHOLD_SME_MANUFACTURED_OPTIONAL` | 중소기업 제조품목 선택 적용 구간 검토 | `partial_mapped` | 1 / 1 | 물품 다수공급자계약 업무처리규정<br>낙동강유역환경청 레미콘ㆍ아스콘 다수공급자계약 2단계경쟁 업무처리기준 | 중소기업 제조품목 | Yes |
| `R_MAS_BELOW_SECOND_STAGE_LOCAL_SUPPLIER_REVIEW` | 2단계경쟁 대상 금액 미만 지역업체 후보 조회 | `partial_mapped` | 1 / 1 | 물품 다수공급자계약 업무처리규정<br>낙동강유역환경청 레미콘ㆍ아스콘 다수공급자계약 2단계경쟁 업무처리기준 | 직접 납품요구, 2단계경쟁 예외 | No |
| `R_MAS_SECOND_STAGE_EVALUATION_METHOD_REVIEW` | MAS 2단계경쟁 종합평가·표준평가 방식 검토 | `partial_mapped` | 1 / 1 | 물품 다수공급자계약 업무처리규정<br>낙동강유역환경청 레미콘ㆍ아스콘 다수공급자계약 2단계경쟁 업무처리기준 | 표준평가방식 | No |
| `R_MAS_LOCAL_SUPPLIER_CANDIDATE_LOOKUP` | MAS·종합쇼핑몰 내 지역업체 후보 조회 | `company_api_mapping_required` | 1 / 0 | 국가종합전자조달시스템 종합쇼핑몰 운영규정 | 지역업체 등록현황 | No |

### Category: `item_eligibility`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_EXPLICIT_ITEM_ELIGIBILITY` | 중기경쟁제품·직접생산확인 추가 검토 | `partial_mapped` | 1 / 0 | 중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역 | 직접생산확인증명서 | No |
| `R_TECH_DEVELOPMENT_PRODUCT_REVIEW` | 기술개발제품·성능인증·혁신제품 확인 | `partial_mapped` | 2 / 0 | 중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙<br>혁신제품 구매 운영 규정 | 성능인증 | No |

### Category: `candidate_lookup`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_COMPANY_CANDIDATE_LOOKUP_GOODS` | 물품 후보업체 조회 | `company_api_mapping_required` | 0 / 0 | None | None | No |
| `R_COMPANY_CANDIDATE_LOOKUP_SERVICE` | 용역 후보업체 조회 | `company_api_mapping_required` | 0 / 0 | None | None | No |
| `R_COMPANY_CANDIDATE_LOOKUP_CONSTRUCTION` | 공사 면허업체 후보 조회 | `company_api_mapping_required` | 0 / 0 | None | None | No |

### Category: `validation`

| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |
|---------|------|--------|--------------------------|----------------|-----------------|------------------------|
| `R_BUYER_TYPE_LOW_CONFIDENCE` | 기관유형 확인 필요 | `partial_mapped` | 0 / 3 | 국가계약분쟁조정위원회 운영규정<br>국가계약 시범특례 운영 지침<br>지방계약 전문기관 지정 | 공공기관운영법 | No |

