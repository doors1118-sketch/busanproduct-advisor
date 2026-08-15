# 지역기업 추천 API 명세

작성일: 2026-06-09  
대상 서비스: 지역기업 검색 지원 / 업체추천 백엔드  
기준 구현: `/vendor-recommendations/search`

## 목적

품목명, 면허명, 업종명, 정책기업 조건을 입력하면 부산 지역 계약 검토 후보 업체와 품목 정책 요약을 반환한다.

이 API는 계약 가능 여부를 확정하지 않는다. 면허, 직접생산증명서, MAS/종합쇼핑몰 계약상태, 정책기업 지위, 인증 유효성은 공고 또는 계약 전 원천자료로 재확인해야 한다.

## 설계 원칙

- LLM을 사용하지 않는다.
- 업체 후보는 내부 업체 DB에서만 조회한다.
- 품목 정책 요약은 `product_policy_summary`를 우선 조회한다.
- 법령 해석, 계약방법 확정, 수의계약 가능성 판단은 별도 계약검토 서비스에서 처리한다.
- 정책기업 조건이 일반 후보 목록에서 확인되지 않으면 `policy_companies.json` 보조 DB에서 별도 확인 후보를 반환한다.

## Endpoint

### `GET /vendor-recommendations/search`

#### Query Parameters

| 이름 | 타입 | 기본값 | 설명 |
| --- | --- | --- | --- |
| `q` | string | 필수 | 검색어. 품목, 면허, 업종, 정책기업 조건을 입력한다. 예: `LED`, `장애인기업 청소용역`, `전기공사업` |
| `region` | string | `부산` | 지역 필터. `busan` 또는 `부산` 사용 가능 |
| `limit` | integer | `30` | 반환 후보 수. 서버에서 1~100으로 제한 |
| `budget_krw` | integer | null | 예산 금액. 원 단위 |
| `include_product_policy` | boolean | `true` | 품목 정책 요약 조회 여부 |

#### Example Request

```http
GET /vendor-recommendations/search?q=장애인기업%20청소용역&region=busan&limit=10&budget_krw=50000000&include_product_policy=true
```

#### Top-Level Response

| 필드 | 설명 |
| --- | --- |
| `query` | 원 검색어 |
| `region` | 적용 지역 |
| `budget_krw` | 정규화된 원 단위 예산 |
| `budget_label` | 예산 표시 문자열 |
| `limit` | 적용된 후보 수 제한 |
| `count` | 반환된 일반 후보 수 |
| `rows` | 일반 업체 후보 목록 |
| `search_plan` | 검색어 정규화 및 확장 계획 |
| `item_policy_summary` | 품목 정책 요약 |
| `product_policy_checks` | 세부품명 기준 정책 매칭 결과 |
| `policy_preference_summary` | 여성기업/장애인기업/사회적기업 조건 확인 요약 |
| `policy_company_alternative_count` | 정책기업 보조 DB 별도 후보 수 |
| `policy_company_alternatives` | 일반 후보 목록 외 별도 정책기업 확인 후보 |
| `mode` | `vendor_recommendation_only` |
| `llm_used` | 항상 `false` |
| `limitations` | API 한계 및 재확인 안내 |

## `rows[]` 주요 필드

| 필드 | 설명 |
| --- | --- |
| `company_name` | 업체명 |
| `location` | 소재지 |
| `main_products` | 대표 품목 |
| `license_or_business_type` | 면허/업종 정보 |
| `contract_review_types` | 후보가 필요한 검토 유형 |
| `budget_review_hint` | 입력 예산 기준 검토 힌트 |
| `shopping_mall_status_label` | 종합쇼핑몰 등록정보 유무 |
| `shopping_mall_product_summary` | 종합쇼핑몰 등록품목 요약 |
| `mas_status_label` | MAS 등록정보 유무 |
| `mas_product_summary` | MAS 등록품목 요약 |
| `direct_production_certificate_status` | 직접생산증명서 정보 유무 |
| `direct_production_certificate_products` | 직접생산증명서 품목 요약 |
| `policy_company_labels` | 일반 후보 DB 기준 정책기업 라벨 |
| `certified_product_labels` | 기술개발제품/인증제품 라벨 |
| `sme_competition_product_label` | 업체 후보 기준 중기간 경쟁제품 표시 |
| `cooperative_purchase_route_label` | 조합추천/소기업 공동사업제품 검토 안내 |
| `recommended_checks` | 공고 전 확인사항 |
| `matched_query_label` | 후보가 매칭된 검색어/검색타입 |
| `review_score` | 내부 정렬 점수 |

## `item_policy_summary`

품목 자체가 중소기업자간 경쟁제품인지, 직접생산증명서 확인이 필요한지, 조합추천/소기업 공동사업제품 경로 검토가 가능한지를 요약한다.

주요 필드:

- `status`
- `message`
- `sme_competition_product`
- `direct_production_certificate`
- `cooperative_purchase_route`
- `matched_products[]`

`matched_products[]`에는 세부품명번호, 세부품명, 중기간 여부, 직접생산 유효 공급업체 수, MAS 공급업체 수 등이 포함된다.

## `policy_company_alternatives[]`

일반 후보 목록에는 요청한 정책기업 지위가 없지만, 별도 정책기업 DB에서 같은 품목/업종 조건으로 후보가 검색될 때 반환한다.

예: `장애인기업 청소용역` 검색 시 일반 후보 목록에는 장애인기업이 없더라도 보조 DB에서 장애인기업 청소 후보를 별도 반환할 수 있다.

주요 필드:

| 필드 | 설명 |
| --- | --- |
| `company_name` | 업체명 |
| `location` | 소재지 |
| `policy_labels` | 정책기업 라벨 |
| `representative_product` | 대표 세부품명 |
| `industry` | 대표 업종 |
| `business_type` | 기업 구분 |
| `manufacturer` | 제조업체 여부 |
| `registered_at` | 나라장터 등록일 |
| `matched_terms` | 검색어와 매칭된 품목/업종 키워드 |
| `source` | `policy_companies_json` |

주의: 이 후보는 일반 후보 DB와 같은 근거 묶음이 아니다. 정책기업 조건을 만족할 가능성이 있는 별도 확인 후보이며, 실제 계약 검토 전 원천자료 확인이 필요하다.

## 현재 성능 기준

2026-06-09 서버 QA 기준:

- 100개 질의: `100/100 OK`
- 평균 응답시간: `938.4ms`
- 최대 응답시간: `2,531ms`
- 품목정책 필수 케이스: `product_policy_summary 49/49`
- LLM 사용: `false`

## 제한사항

- 고정 QA 100개 통과가 모든 자유질의 통과를 의미하지 않는다.
- 동시접속 부하테스트는 별도 수행이 필요하다.
- 정책기업 보조 DB는 별도 확인 후보 제공 목적이며 일반 후보 DB의 모든 상세 속성을 포함하지 않는다.
- 법령 해석, 계약방법 판단, 수의계약 가능성 확정은 이 API 범위 밖이다.
- 외부 제공 시 인증, 접근제어, rate limit, 감사로그 정책을 별도 적용해야 한다.
