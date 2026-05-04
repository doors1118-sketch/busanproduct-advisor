# Item Eligibility Schema Change Report (v0.1 -> v0.1.1)

본 문서는 Phase 7-B/7-C 보완 작업으로 설계된 품목 기반 적격성 검증 스키마가 v0.1.1로 업그레이드되면서 변경된 주요 내역을 기록합니다.

## 주요 보강 내역

### 1. `item_alias_map` 보강
단순한 1:N 매핑을 넘어, 자연어 처리(NLP) 기반의 해소율을 높이기 위해 메타데이터 필드가 대폭 추가되었습니다.
- **`alias_normalized` 추가**: 특수문자나 띄어쓰기가 제거된 정규화 명칭 보관.
- **`alias_type` 추가**: 동의어의 유형(`common_name` 일반명, `slang` 은어, `acronym` 약어 등) 구분.
- **`match_confidence`, `display_rank` 추가**: 후보군이 여러 개 도출될 때 사용자에게 먼저 보여줄 우선순위 산정.

### 2. 이력(History) 관리 강화 (PK 구조 변경)
`item_id` 또는 복합키 기반이었던 구조를 고유 식별자(PK) 기반으로 변경하여 이력을 완벽히 보존합니다.
- **`sme_competition_product_item`**: `item_id` PK → `designation_id` PK. (동일 품목이라도 해마다 지정 이력이 다를 수 있음을 반영)
- **`direct_production_requirement`**: `item_id` PK → `requirement_id` PK. 유효기간(`effective_from`, `effective_to`), `version_hash`, 그리고 기준 조문(`standard_article_ref`) 필드를 신설하여 개정 이력 추적.
- **`company_direct_production_cert_mapping`**: `(company_id, detail_item_code)` 복합 PK → `cert_mapping_id` 단일 PK. 동일 품목에 대한 인증의 갱신/만료/재취득 이력을 독립 레코드로 쌓을 수 있도록 변경.

### 3. 극단적 PII 보완 방어막
- 사업자등록번호(`business_number`)와 인증서발급번호(`cert_number`)의 원문 텍스트 저장을 스키마 단에서 원천 차단했습니다.
- 오직 `business_number_hash`와 `cert_number_hash` 필드만 존재하며, 이는 단방향 암호화되어 교차검증(Verification) 용도로만 사용됩니다.

## 운영 정책 결속(Binding)
위의 스키마 변경에도 불구하고 아래의 핵심 제약사항은 유지됩니다.
- "detail_item_code가 확정되지 않으면 법적 판단 보류 (Interactive Resolution)"
- "직접생산확인을 보유했다는 이유만으로 계약 가능 여부 단정 금지"
