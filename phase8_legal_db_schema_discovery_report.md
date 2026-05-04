# Phase 8 Legal DB Schema Discovery Report

본 문서는 `legal_db_v0_1_3.sqlite`에 대한 읽기 전용 스키마 탐색(Schema Discovery) 결과를 요약한 보고서입니다.

## 1. 개요
- DB 경로: `app/data/legal_db_v0_1_3.sqlite`
- 탐색 방법: `sqlite_master` 및 `PRAGMA table_info`를 이용한 Read-Only 쿼리
- 출력물: `phase8_legal_db_schema_map.json`

## 2. 테이블 목록 및 주요 매핑 구조
총 7개의 테이블이 식별되었습니다.

1. **`legal_source` (핵심 테이블)**: 법령/지침 등의 본문 메타데이터
2. **`legal_jurisdiction_mapping`**: 관할 구역 매핑 (`source_id` <-> `jurisdiction_scope`)
3. **`legal_buyer_type_mapping`**: 구매자 유형 매핑 (`source_id` <-> `buyer_type_scope`)
4. **`legal_overlay_mapping`**: 조달 경로(Overlay) 매핑 (`source_id` <-> `overlay_scope`)
5. **`legal_relation`**: 법령 간 관계 정보
6. **`legal_source_seed_mapping`**: 시드 기반 매핑 정보
7. **`sqlite_sequence`**: 자동 증가 시퀀스 관리 테이블

## 3. 핵심 컬럼 점검 결과

### 3.1. 식별 및 표출 컬럼
`legal_source` 테이블 내에 다음 핵심 정보가 존재함을 확인했습니다.
- `source_id`
- `source_name`
- `normalized_title`

### 3.2. 상태 및 속성 플래그 컬럼
`legal_source` 테이블 내에 다음 제어 플래그 컬럼들이 존재합니다.
- `active_for_rule` (Rule Engine 판단용 활성화 여부)
- `active_for_procedure` (절차 안내용 활성화 여부)
- `judgment_eligible` (계약 판단 근거 가능 여부)
- `activation_mode` (활성화 모드 - default, overlay 등)

### 3.3. 매핑 구조 검증
- **`buyer_type` 맵핑**: 단일 컬럼 조인이 아닌 별도의 브릿지 테이블 `legal_buyer_type_mapping`을 통해 다대다 관계로 조인해야 합니다.
- **`procurement_route` (Overlay) 매핑**: 브릿지 테이블 `legal_overlay_mapping`을 통해 `overlay_scope`를 관리합니다.
- **절차 전용(Procedure Only) 구분**: `legal_source` 테이블의 `active_for_procedure` 플래그와 `judgment_eligible` 속성을 통해 필터링이 가능합니다.

## 4. 데이터 분포 현황 (Review Status)
`legal_source` 테이블의 `review_status` 분포는 다음과 같습니다.
- `verified`: 31건
- `candidate_needs_review`: 183건
- `needs_manual_source`: 2건
- `wrong_match`: 1건

> [!NOTE]
> 실 DB 연동 시 `review_status = 'verified'` 조건만을 조회하도록 필터링을 적용해야 할 수 있습니다.

## 5. 결론 및 다음 단계
Gateway 3종 Resolver(Source, Route, Procedure)가 요구하는 모든 컬럼(`active_for_rule`, `active_for_procedure`, 브릿지 매핑 테이블 등)이 명확히 존재하므로, 즉각적인 Read-Only Resolver 구현이 가능함을 확인했습니다.

**다음 진행 단계**:
- **Source Resolver 구현**: `legal_source`와 `legal_buyer_type_mapping` 테이블을 조인하여 조건에 맞는 Base Source 조회
- **Route Resolver 구현**: `legal_overlay_mapping` 테이블을 조인하여 Overlay Source 조회
- **Procedure Resolver 구현**: `active_for_procedure = 1` 인 항목만 선별 조회
