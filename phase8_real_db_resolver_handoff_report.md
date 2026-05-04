# Phase 8 Real-DB Resolver Handoff Report

본 문서는 `legal_db_v0_1_3.sqlite` 스키마를 바탕으로 Phase 8 Gateway Skeleton의 핵심 리졸버 3종을 실제 DB(Read-Only) 기반으로 전환하는 작업을 성공적으로 완료하고 그 결과를 기록한 Handoff Report입니다.

## 1. 구현 요약
- **Source Resolver**: `legal_source`와 `legal_buyer_type_mapping` 조인. `buyer_type` Fallback 처리 및 Broad 매칭 기반의 `contract_object_scope` 필터를 적용한 실제 조회 로직 구현
- **Route Resolver**: `legal_overlay_mapping` 테이블을 조인하여 Overlay Source를 판별하고, `dual_routing=True` 처리 등 조달 경로 제어 로직 구현 (`resolve_route`로 함수명 통합)
- **Procedure Resolver**: 절차 전용 항목(`active_for_procedure=1`, `judgment_eligible=0`)을 선별하여 `answer_builder_procedure_section_only` 속성을 강제 할당하는 쿼리 구현
- **Item / Company Resolver**: 의존 데이터 구조 확정 전까지 기존 상태와 동일하게 **Mock 유지**

## 2. 보안 및 방어 구조 (No-Mutation Policy)
`app/gateway/db/reader.py` (ReadOnlyDatabase)를 통해 **절대적인 No-Mutation 정책**을 유지하고 있습니다.
1. **URI 모드**: `file:?mode=ro`
2. **PRAGMA**: `query_only=ON`
3. **Authorizer**: `sqlite3.set_authorizer`를 통한 모든 변조 및 DDL 작업 차단
4. **Keyword 필터**: 정규식을 통한 위험 키워드 차단
5. **쿼리 인터페이스 통제**: 직접적인 Cursor 접근을 금지하고, `db_reader.execute(query, params)` 메서드로 파라미터화된 쿼리만 허용

## 3. 테스트 및 검증 현황
### 3.1. 통과 완료된 항목 (100% Pass)
- [x] Mock 기반 Schema Validation (Trigger/Enrichment 로직 등)
- [x] DB 변조 및 Write Query 차단 테스트
- [x] Real-DB Smoke Test (Source, Route, Procedure 리졸버의 Invariant 및 플래그 강제 할당)
- [x] Real-DB 환경에서의 `GatewayResponse` JSON Schema 정합성 검증 (`jsonschema.validate`)

### 3.2. 아직 검증하지 않은 범위 (Out of Scope for Phase 8)
- `procedure_topic` 필터에 대한 실제 쿼리 연동 (현재 Taxonomy 스펙 미정으로 보류 상태)
- 다양한 `buyer_type` / `procurement_route` 조합에 따른 엣지 케이스 로드 테스트
- 실제 Item/Company 카탈로그 DB 연동 및 Enrichment 속도/정합성 테스트

## 4. 다음 단계 제언
본 Gateway 파이프라인의 핵심인 법령/절차 Base 데이터가 안전하게 확보되었습니다.
이어질 구현 단계로는 다음 2가지 방향을 제안합니다.

1. **Rule Engine v0.1 연동 (Decision Mapping)**
   - 본 GatewayResponse를 입력으로 받아, `active_for_rule=True` 항목에 대해 Rule Engine(예: `decision_engine.py`)이 실제 적격성/법령 위반 여부를 판단하는 파이프라인 연계
2. **Item / Company DB 구조 설계 및 리졸버 전환**
   - 여전히 Mock으로 동작하고 있는 Item / Company Resolver를 실 데이터 기반으로 교체하기 위한 카탈로그 DB 구조 수립 및 연동 작업
