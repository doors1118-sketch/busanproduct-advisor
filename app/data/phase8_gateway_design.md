# Phase 8 Internal Legal MCP Gateway — 설계 문서

> **작성일**: 2026-05-04  
> **기준선**: Phase 7 Final Baseline (`phase7_final_baseline_manifest.json`)  
> **준수 정책**: `phase7_no_mutation_policy.md` (A9 조건 충족)

---

## 1. Gateway란 무엇인가

Gateway는 **Rule Engine 이전에 위치하는 read-only 조회 계층**입니다.

```
사용자 질문
    │
    ▼
┌─────────────────────────────────────────────┐
│  Internal Legal MCP Gateway (Phase 8)       │
│                                             │
│  입력: 슬롯(buyer_type, amount, item 등)     │
│  출력: context 번들 (source / route / item / │
│        company context)                     │
│                                             │
│  ❌ 판단하지 않음                             │
│  ❌ DB를 수정하지 않음                        │
│  ❌ LLM 답변을 생성하지 않음                  │
│  ✅ 조회 결과만 반환                          │
└──────────────┬──────────────────────────────┘
               │ context 번들
               ▼
┌─────────────────────────────────────────────┐
│  Rule Engine (❶~❽)                          │
│                                             │
│  context 번들을 소비하여                      │
│  rule evaluation / candidate decision       │
│                                             │
│  ❌ 자연어 답변 생성하지 않음                  │
│  ✅ 판단 결과(decision context)만 출력         │
└──────────────┬──────────────────────────────┘
               │ decision context
               ▼
┌─────────────────────────────────────────────┐
│  Answer Builder                             │
│                                             │
│  decision context를 소비하여                 │
│  자연어 답변 생성                             │
│                                             │
│  trigger_grade별 노출 수준 적용               │
└─────────────────────────────────────────────┘
```

### Gateway가 하는 것
- legal_db_v0_1_3.sqlite에서 **read-only SELECT** 쿼리 실행
- 슬롯 값에 따라 **관련 법령 source, 조달경로 overlay, item eligibility context, 업체 후보 context**를 조합
- 조합된 context를 **구조화된 JSON 번들**로 Rule Engine에 전달

### Gateway가 하지 않는 것
- 계약 가능/불가능 판단
- "수의계약 가능합니다" 같은 법적 결론 생성
- DB INSERT / UPDATE / DELETE
- LLM 호출 또는 자연어 답변 생성
- 외부 API 호출 (법제처 API, 조달청 API 등)

---

## 2. 아키텍처

### 2.1 위치

```
┌─────────┐     ┌───────────┐     ┌─────────────┐     ┌───────────┐
│ Slot    │     │ Gateway   │     │ Rule Engine │     │ Answer    │
│ Parser  │────▶│ (Phase 8) │────▶│ (❶~❽)      │────▶│ Builder   │
│         │     │           │     │             │     │           │
│ 사용자  │     │ read-only │     │ rule eval   │     │ 자연어    │
│ 질문    │     │ context   │     │ candidate   │     │ 답변 생성 │
│ 분석    │     │ 조회      │     │ decision    │     │           │
└─────────┘     └───────────┘     └─────────────┘     └───────────┘
```

**역할 분리 원칙**:
- **Rule Engine**: rule evaluation, candidate decision만 수행. 자연어 답변을 생성하지 않음.
- **Answer Builder**: Rule Engine의 decision context를 소비하여 자연어 답변을 생성. trigger_grade별 노출 수준 적용.

Slot Parser는 사용자 질문에서 슬롯(buyer_type, contract_object, amount 등)을 추출합니다. Gateway는 이 슬롯을 입력으로 받아 context를 조회합니다.

### 2.2 모듈 구조

```
app/gateway/                          ← Phase 8 신규 module (별도 디렉토리)
├── __init__.py
├── gateway.py                        ← Gateway 진입점
├── resolvers/
│   ├── __init__.py
│   ├── source_resolver.py            ← Source Context 조회
│   ├── route_resolver.py             ← Route Layer 해소
│   ├── item_resolver.py              ← Item Eligibility Context 조회
│   └── company_resolver.py           ← Company Candidate Context 조회
├── models/
│   ├── __init__.py
│   ├── slots.py                      ← 입력 슬롯 데이터 모델
│   └── context.py                    ← 출력 context 데이터 모델
├── db/
│   ├── __init__.py
│   └── reader.py                     ← read-only DB 접근 계층
└── tests/
    ├── __init__.py
    ├── test_source_resolver.py
    ├── test_route_resolver.py
    ├── test_item_resolver.py
    └── test_company_resolver.py
```

### 2.3 의존 관계

```
gateway.py
    ├── source_resolver.py ──→ legal_source 테이블 (SELECT only)
    │                         legal_jurisdiction_mapping
    │                         buyer_type_mapping_table [TBD: 실제 테이블명 schema 확인 필요]
    │
    ├── route_resolver.py  ──→ legal_overlay_mapping
    │                         procurement_route_scope_map (JSON config)
    │
    ├── item_resolver.py   ──→ item_alias_map (향후)
    │                         sme_competition_product_item (향후)
    │                         company_direct_production_cert_mapping (향후)
    │
    ├── company_resolver.py ──→ 업체 DB (기존 모니터링 시스템 DB, read-only)
    │
    └── procedure_resolver.py ──→ legal_source (active_for_procedure=1, active_for_rule=0)
```

> **[TBD] 테이블명 정합성**: `legal_buyer_type_mapping`(DB schema)과 `legal_buyer_type_scope_map`(JSON config)의 명칭이 혼재되어 있음. 구현 시 실제 schema 기준으로 통일 필요.

---

## 3. 4대 Resolver 설계

### 3.1 Source Resolver

**역할**: 슬롯에 따라 관련 법령 source 목록을 조회합니다.

**입력 슬롯**:
- `buyer_type`: 기관유형 (local_government, national_government, public_institution)
- `contract_object`: 계약목적물 (construction, goods, service)
- `procurement_route`: 조달경로 (자체계약, 조달청의뢰, MAS, 쇼핑몰 등)

**buyer_type 미제공 처리**:
- buyer_type가 미제공(null)이면 local_contract를 **조용히 확정하지 않음**.
- `assumed_buyer_type = "local_government"`, `assumption_reason`, `confidence = "low"`, `required_slots_missing = ["buyer_type"]`를 source_context에 포함.
- Rule Engine에는 **기관유형 미확정 상태**로 전달하여 추가 질문 유도.

**조회 로직**:
```sql
-- Step 1: buyer_type으로 jurisdiction 결정
-- [TBD] 실제 테이블명은 schema 확인 후 확정
SELECT jurisdiction_scope
FROM buyer_type_mapping_table  -- TBD: legal_buyer_type_mapping 또는 별도 config
WHERE buyer_type_scope = :buyer_type;

-- Step 2: 해당 jurisdiction의 active source 조회
SELECT ls.*
FROM legal_source ls
JOIN legal_jurisdiction_mapping ljm ON ls.source_id = ljm.source_id
WHERE ljm.jurisdiction_scope = :jurisdiction
  AND ls.active_for_rule = 1
  AND ls.review_status NOT IN ('wrong_match', 'needs_manual_source');
  -- [NOTE] review_status 허용값 enum은 실제 DB 확인 필요.
  -- 현재 원칙: wrong_match, needs_manual_source 제외. 나머지는 허용.

-- Step 3: overlay가 있으면 추가 source 조회
SELECT ls.*
FROM legal_source ls
JOIN legal_overlay_mapping lom ON ls.source_id = lom.source_id
WHERE lom.overlay_scope = :overlay_scope
  AND ls.active_for_rule = 1;
```

**출력**: `SourceContext` — 관련 법령 source 목록 + 메타데이터 + buyer_type assumption 정보

**제약**:
- SELECT만 사용. INSERT/UPDATE/DELETE 금지.
- `active_for_rule = 0`인 source는 source_context에 포함하지 않음 (procedure_context에서 별도 처리).
- `review_status`가 `wrong_match`, `needs_manual_source`인 source는 반환하지 않음.
- `review_status` 허용값 enum은 실제 DB 확인 필요. 구현 시 enum 목록을 config로 관리.

### 3.2 Route Resolver

**역할**: 조달경로에 따른 Overlay 해소를 수행합니다.

**입력 슬롯**:
- `buyer_type`: 기관유형
- `procurement_route`: 조달경로

**조회 로직**:
```
1. buyer_type → base_jurisdiction 결정 (buyer_type_mapping_table [TBD])
2. procurement_route가 조달청 경로인지 확인 (procurement_route_scope_map)
3. 조달청 경로이면:
   - base_jurisdiction의 법령 source (기본 법령)
   - procurement_route에 해당하는 overlay source (조달청 기준)
   - 두 source 집합을 병합하여 반환
4. 자체 계약 경로이면:
   - base_jurisdiction의 법령 source만 반환
   - overlay 없음
```

**출력**: `RouteContext` — base sources + overlay sources + 이중 라우팅 여부

**제약**:
- `procurement_route_layer_policy.md` 준수
- 조달청 기준이 기본 법령을 **대체하지 않음** (병합만)
- `procurement_route_required` 조건 미충족 시 overlay 미발동

### 3.3 Item Resolver

**역할**: Item Eligibility 트리거 판정 및 eligibility_context 생성.

**입력 슬롯**:
- `user_query`: 사용자 질문 원문
- `item_name`: 추출된 품목명 (있으면)
- `detail_item_code`: 세부품명번호 (있으면)
- `company_id`: 후보 업체 ID (있으면)

**조회 로직**:
```
1. 트리거 판정 (item_eligibility_trigger_policy_v0_1_4.md 기준):
   a. T1: user_query에 트리거 키워드 포함? → Explicit
   b. T2: detail_item_code 제공? → Explicit
   c. T5: 계약경로상 중기경쟁 검증 필수? → Explicit
   d. T3: item_alias_map 해소 결과 중기경쟁 후보? → Silent
   e. 모두 미충족 → item_eligibility_required = false

2. 트리거 발동 시:
   a. item_alias_map에서 세부품명 후보 조회
   b. sme_competition_product_item에서 경쟁제품 여부 확인
   c. company_id 있으면 company_direct_production_cert_mapping 조회

3. eligibility_context 생성
```

**출력**: `ItemEligibilityContext` — trigger_grade + eligibility_context (또는 null)

**제약**:
- `item_eligibility_trigger_policy_v0_1_4.md` 준수
- 트리거 미발동 시 eligibility_context = null 반환 (스킵)
- 결과는 **후보 분류 정보**. 계약 가능/불가능 판단 금지.
- Silent 트리거 시 trigger_grade = "silent" 명시.

### 3.4 Company Resolver

**역할**: 지역업체 후보 검색 및 T4 Enrichment 처리.

**입력 슬롯**:
- `item_name`: 품목명 (있으면)
- `location`: 지역 (기본: 부산)
- `company_id`: 특정 업체 ID (있으면)

**조회 로직**:
```
1. 업체 DB에서 지역·품목 기준 후보 검색
2. 후보 목록 생성 (업체명, 소재지, 업종, 실적)
3. T4 Enrichment:
   a. 각 후보 업체에 대해 company_direct_production_cert_mapping 조회
   b. 직생 데이터 있으면 enrichment_data 첨부
   c. 없으면 첨부 안 함
```

**출력**: `CompanyCandidateContext` — 후보 목록 + enrichment_data (있으면)

**제약**:
- `company_candidate_enrichment_policy.md` 준수
- 직생 데이터 존재가 계약 판단에 **영향 없음**
- 직생 미확인 업체를 **배제하지 않음**
- Enrichment는 후보표 optional column 용도로만 사용

---

## 4. Gateway 입출력 설계

### 4.1 입력: GatewayRequest

```json
{
  "request_id": "uuid",
  "user_query": "8천만원 물품 수의계약 가능한가?",
  "slots": {
    "buyer_type": "local_government",
    "contract_object": "goods",
    "amount": 80000000,
    "procurement_route": null,
    "contract_method": "direct_contract",
    "item_name": null,
    "detail_item_code": null,
    "company_id": null,
    "location": "부산"
  }
}
```

### 4.2 출력: GatewayResponse

```json
{
  "request_id": "uuid",
  "gateway_version": "v0.1.0",
  "baseline_db": "legal_db_v0_1_3.sqlite",
  "source_context": {
    "sources": [ ... ],
    "assumed_buyer_type": "local_government",
    "assumption_reason": "부산시 업무 기본 맥락에 따른 임시 추정",
    "buyer_type_confidence": "low",
    "required_slots_missing": ["buyer_type"]
  },
  "route_context": { ... },
  "procedure_context": {
    "sources": [ ... ],
    "usage": "answer_builder_procedure_section_only",
    "judgment_eligible": false
  },
  "item_eligibility_context": null,
  "company_candidate_context": null,
  "metadata": {
    "total_sources_matched": 12,
    "procedure_sources_matched": 3,
    "overlay_applied": false,
    "item_eligibility_required": false,
    "item_eligibility_trigger_grade": null,
    "company_candidates_found": 0,
    "enrichment_applied": false
  }
}
```

상세 스키마는 `phase8_gateway_response_schema.json`에 정의합니다.

---

## 5. 데이터 흐름 시퀀스

### 시퀀스 1: 일반 금액·계약방식 질문

```
"8천만원 물품 수의계약 가능한가?"

Slot Parser
  → buyer_type: (미확정 또는 local_government)
  → contract_object: goods
  → amount: 80000000
  → contract_method: direct_contract

Gateway
  ├── Source Resolver
  │     → buyer_type=local_government → jurisdiction=local_contract
  │     → active_for_rule=1 source 조회 → 12건 반환
  │
  ├── Route Resolver
  │     → procurement_route=null → overlay 미적용
  │     → base sources만 반환
  │
  ├── Item Resolver
  │     → 트리거 키워드 없음, 세부품명 없음 → item_eligibility_required=false
  │     → eligibility_context=null
  │
  └── Company Resolver
        → item_name 없음, company_id 없음 → 미실행
        → company_candidate_context=null

→ Rule Engine에 context 번들 전달
→ Rule Engine이 ❶~❼로 rule evaluation (❽ 스킵)
→ Answer Builder가 decision context로 자연어 답변 생성
```

### 시퀀스 2: 직생 명시 + 업체 검색

```
"CCTV 부산업체 찾아줘. 직생도 봐줘."

Slot Parser
  → item_name: CCTV
  → location: 부산
  → trigger keyword: "직생"

Gateway
  ├── Source Resolver
  │     → 기본 법령 source 조회
  │
  ├── Route Resolver
  │     → 기본 경로
  │
  ├── Item Resolver
  │     → T1 발동 (키워드 "직생") → trigger_grade=explicit
  │     → item_alias_map: CCTV → 세부품명 후보 반환
  │     → 세부품명 미확정 → eligibility_context.detail_item_resolved=false
  │
  └── Company Resolver
        → item_name=CCTV, location=부산 → 후보 업체 검색
        → T4 Enrichment: 직생 데이터 있는 업체 enrichment_data 첨부

→ Rule Engine에 context 번들 전달
→ Rule Engine이 ❶~❽ rule evaluation (Explicit이므로 ❽ 포함)
→ Answer Builder가 Explicit 등급으로 직생 섹션 전면 표시
```

### 시퀀스 3: 일반 품목명 (Silent)

```
"컴퓨터 구매 방법 알려줘"

Gateway
  ├── Item Resolver
  │     → 키워드 없음, 세부품명 없음
  │     → T3: item_alias_map → 컴퓨터 → 중기경쟁 후보 감지
  │     → trigger_grade=silent
  │     → eligibility_context 생성 (내부 분류용)
  │
  └── ...

→ Rule Engine: ❶~❼ rule evaluation + ❽ Silent (내부 분류만)
→ Answer Builder: 보조 문구 1줄만 답변 말미에 표시
```

---

## 6. DB 접근 원칙

### 6.1 read-only 강제

```python
# db/reader.py — 설계 의도
import sqlite3

class LegalDBReader:
    """read-only DB 접근 계층. INSERT/UPDATE/DELETE를 원천 차단."""

    def __init__(self, db_path: str):
        # read-only 모드로 연결
        self.conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.conn.row_factory = sqlite3.Row

    def execute(self, query: str, params: tuple = ()) -> list:
        """SELECT 쿼리만 허용. DML 감지 시 예외 발생."""
        normalized = query.strip().upper()
        if not normalized.startswith("SELECT"):
            raise PermissionError(
                f"Gateway는 SELECT만 허용합니다. 감지된 쿼리: {normalized[:50]}"
            )
        cursor = self.conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchall()

    def close(self):
        self.conn.close()
```

### 6.2 접근 가능 테이블

| 테이블 | 접근 | 용도 |
|--------|:----:|------|
| `legal_source` | ✅ SELECT | source 메타데이터 조회 (source_context + procedure_context) |
| `legal_jurisdiction_mapping` | ✅ SELECT | jurisdiction 매핑 |
| `buyer_type_mapping_table` [TBD] | ✅ SELECT | buyer_type → jurisdiction |
| `legal_overlay_mapping` | ✅ SELECT | overlay 매핑 |
| `legal_relation` | ✅ SELECT | 법령 간 관계 조회 |
| 기타 모든 테이블 | ❌ WRITE | INSERT/UPDATE/DELETE 금지 |

---

## 7. 에러 처리

Gateway는 조회 실패 시에도 **Rule Engine 실행을 차단하지 않습니다**.

| 상황 | Gateway 동작 | Rule Engine / Answer Builder 영향 |
|------|-------------|-----------------------------------|
| buyer_type 미제공 | assumed_buyer_type 포함 + confidence="low" + required_slots_missing=["buyer_type"] | Rule Engine이 기관유형 미확정 상태로 처리. Answer Builder가 추가 질문 유도 |
| DB 연결 실패 | 빈 context 반환 + error 필드에 사유 기록 | Rule Engine이 fallback 동작 |
| 매칭 source 0건 | 빈 sources 배열 반환 | Answer Builder가 "관련 법령 미발견" 안내 |
| item_alias_map 미구축 | item_eligibility_context = null | ❽ 스킵 |
| 업체 DB 조회 실패 | company_candidate_context = null | Answer Builder가 업체 추천 불가 안내 |

---

## 8. Phase 7 Baseline과의 정합성

| Phase 7 기준 | Gateway 준수 사항 |
|-------------|-------------------|
| legal_db_v0_1_3.sqlite 고정 | read-only 접근만. schema/data 변경 없음 |
| active_for_rule = 63건 | 이 63건만 source_context에 포함 |
| active_for_procedure = 15건 | 이 15건은 procedure_context에 별도 포함. source_context에서 제외 |
| procedure_only 분리 | procedure_context는 Answer Builder 절차 안내 섹션에서만 사용. Rule Engine 판단 근거로 사용 금지 |
| activation_mode 필수 | activation_mode 없는 source는 반환하지 않음 |
| Rule Engine ❶~❽ 순서 | Gateway는 ❶ 이전 단계. 순서에 영향 없음. Rule Engine은 rule evaluation만, Answer Builder가 답변 생성 |
| Item Eligibility v0.1.4 | trigger 판정 로직을 Item Resolver에 내장 |
| T3 Silent | trigger_grade = "silent" 명시. 노출 수준은 Answer Builder가 결정 |
| T4 Enrichment | Company Resolver에서 후보 조회 후 별도 실행 |
| No-Mutation Policy | A9 조건 7개 모두 충족 |

---

## 9. Procedure Context 설계

### 9.1 목적

`procedure_only` source(active_for_procedure=1, active_for_rule=0)는 판단근거가 아니므로 source_context에 포함하지 않습니다.
다만 절차 안내(위원회 구성, 물가변동 처리, 제안서 평가 등)용으로 별도 `procedure_context`를 제공합니다.

### 9.2 조회 로직

```sql
SELECT ls.*
FROM legal_source ls
WHERE ls.active_for_procedure = 1
  AND ls.active_for_rule = 0
  AND ls.review_status NOT IN ('wrong_match', 'needs_manual_source');
```

### 9.3 출력 구조

```json
{
  "procedure_context": {
    "sources": [
      {
        "source_id": "...",
        "source_name": "...",
        "source_type": "...",
        "usage": "procedure_guidance_only"
      }
    ],
    "usage": "answer_builder_procedure_section_only",
    "judgment_eligible": false
  }
}
```

### 9.4 사용 규칙

| 소비자 | 사용 가능 | 용도 |
|--------|:---------:|------|
| **Rule Engine** | ❌ 금지 | 판단 근거로 사용 불가 |
| **Answer Builder** | ✅ 허용 | 절차 안내 섹션에서만 사용 |

- `judgment_eligible = false`이므로 계약 방식, 낙찰자 결정 가능 여부를 확정하는 데 사용할 수 없음.
- `procedure_only_separation_policy.md` 준수.

### 9.5 Procedure Resolver 추가

모듈 구조에 `procedure_resolver.py`를 추가합니다:

```
app/gateway/resolvers/
├── source_resolver.py
├── route_resolver.py
├── item_resolver.py
├── company_resolver.py
└── procedure_resolver.py    ← 신규
```

---

## 10. 후속 산출물 예고

| # | 산출물 | 역할 |
|:-:|--------|------|
| 2 | `phase8_gateway_api_spec.md` | Gateway API 엔드포인트·파라미터·응답 상세 스펙 |
| 3 | `phase8_gateway_response_schema.json` | GatewayResponse JSON 스키마 정의 |
| 4 | `phase8_gateway_mock_responses.json` | 12개 테스트 시나리오별 mock response |
| 5 | `phase8_gateway_rule_engine_interface.md` | Gateway 출력 → Rule Engine 입력 매핑 인터페이스 |
| 6 | `phase8_gateway_dry_run_test_plan.md` | dry-run 테스트 계획 및 검증 기준 |
