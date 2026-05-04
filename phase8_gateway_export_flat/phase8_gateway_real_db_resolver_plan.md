# Phase 8 Real-DB Resolver Implementation Plan

본 계획서는 현재 Mock 수준인 Gateway Skeleton을 한 단계 발전시켜, 실제 `legal_db_v0_1_3.sqlite`에 Read-Only로 연결하여 법령 데이터를 추출하는 Resolver 구현을 위한 준비 문서입니다.

## 1. 구현 목표 및 제약 사항
- **구현 대상**: `Source Resolver`, `Route Resolver`, `Procedure Resolver`의 1차 실 DB 연동
- **유지 대상**: `Item Resolver`, `Company Resolver`는 추가 DB 구성을 위한 검토가 완료될 때까지 임시 Mock 상태 유지
- **제약 사항 (Strict Limits)**:
  - 기존 DB Schema (`legal_db_v0_1_3.sqlite`) 변경 절대 금지
  - `INSERT`, `UPDATE`, `DELETE` 변조 금지
  - 외부 API 호출 금지
  - 백그라운드 Scheduler 등록 금지
  - Production 환경 배포(Deployment) 금지

## 2. 모듈별 구현 계획

### 2.1. Source Resolver
- `app/gateway/resolvers/source_resolver.py`에 `ReadOnlyDatabase`를 주입하여 실제 DB 질의 시작.
- **조회 대상**: `base` source type 테이블 (예: 지방계약법, 국가계약법 등)
- `buyer_type`, `contract_object` 조건을 필터링하여 일치하는 법령/규정 `SourceEntry` 리스트를 반환하도록 `SELECT` 구문 작성.

### 2.2. Route Resolver
- **조회 대상**: `overlay` source type 테이블 (예: 조달청 MAS 지침 등)
- `procurement_route` 인자에 맞추어 `overlay_applied` 여부를 판정하고, 해당하는 Overlay 법령 목록을 DB에서 로드하도록 매핑.

### 2.3. Procedure Resolver
- **조회 대상**: `procedure` source type 테이블 (절차 안내 관련 지침)
- `contract_object="construction"`이거나 `procedure_topic`이 유효할 때 절차 항목들을 DB에서 선별 조회하도록 쿼리 구축.

### 2.4. Item / Company Resolver (보류)
- 품목/업체 정보 조회는 `legal_db_v0_1_3`에 포함되지 않을 수 있으므로, 별도의 카탈로그 DB 또는 캐시 테이블 준비 전까지는 **현재의 Mock 로직을 우선 유지**합니다.

## 3. 사전 Schema 확인 필요 항목
실제 `SELECT` 문을 작성하기 앞서 `legal_db_v0_1_3.sqlite` 내에 다음 정보가 어떤 테이블, 어떤 컬럼명으로 적재되어 있는지 검증이 필요합니다.
- `source_id`, `source_name`, `law_category`, `source_type` 매핑 컬럼
- `applicability_scope`와 `buyer_type` 간의 조인/필터링 조건
- 절차(Procedure) 전용 데이터를 구별하는 플래그 존재 여부

## 4. 테스트 계획 (Testing Strategy)
- **Mock Schema Validation 유지**: 기존 작성한 JSON Schema 검증 테스트(`test_phase8_gateway_mock_validation.py`)가 실 데이터 반환 시에도 깨지지 않는지 보장합니다.
- **Read-Only DB Smoke Test 추가**: 
  - `reader.py`를 활용해 실제 `legal_db_v0_1_3.sqlite`에 접속하여 Resolver들이 최소 1개 이상의 유효한 `SourceEntry`를 반환하는지 검증합니다.
- **Mutation Block Test 유지**: Write Query가 철저하게 예외(Exception)를 발생시키는 4중 차단 방어벽 검증 테스트를 계속 유지합니다.
