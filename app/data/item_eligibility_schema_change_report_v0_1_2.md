# Item Eligibility Schema Change Report (v0.1.1 → v0.1.2)

## 주요 변경 내역

### 1. `procurement_item_master`
- `item_group_name` 추가: 품목 분류 그룹명
- `g2b_category_name` 추가: 나라장터 분류명
- `source`, `source_version` 추가: 데이터 원천 추적
- `effective_from`, `effective_to` 추가: 유효기간
- `created_at`, `updated_at` 추가: 감사(Audit) 필드

### 2. `item_alias_map`
- `detail_item_name` 추가: 후보 제시 시 세부품명 표시용
- `created_at`, `updated_at` 추가

### 3. `sme_competition_product_item`
- `source_document_name` 추가: 지정 근거 문서명
- `created_at`, `updated_at` 추가

### 4. `direct_production_requirement`
- `detail_item_name` 추가
- `required_facility_summary`와 `required_process_summary` 분리 (v0.1.1에서는 하나였음)
- `created_at`, `updated_at` 추가

### 5. `company_direct_production_cert_mapping`
- `detail_item_name` 추가
- `source_checked_at` 추가: 인증 확인 시점 기록
- `version_hash` 추가: 동기화 이력 추적
- `created_at`, `updated_at` 추가
- `business_number_hash` 제거: cert_hash만으로 충분하며 불필요한 PII 해시 축소

## 핵심 정책 유지
- detail_item_code 미확정 시 판단 보류
- 직생 보유만으로 계약 가능 단정 금지
- PII 원문 저장 금지
