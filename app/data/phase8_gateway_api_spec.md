# Phase 8 Gateway API Specification

> **버전**: v0.1.1  
> **기준 설계**: `phase8_gateway_design.md` (보완 반영본)  
> **준수 정책**: `phase7_no_mutation_policy.md` (A9)  
> **v0.1.1 변경**: Company Resolver 세부품명 입력, Procedure Resolver 필터, 금지 표현 수정, Route/Source 중복 제거, Item Resolver 상태 세분화

---

## 1. 개요

Gateway는 내부 Python 모듈로, HTTP 엔드포인트가 아닌 **함수 호출 인터페이스**로 동작합니다.
Rule Engine이 Gateway 함수를 직접 호출하여 context 번들을 받습니다.

```python
from app.gateway import resolve_context

response: GatewayResponse = resolve_context(request: GatewayRequest)
```

---

## 2. 진입점 API

### `resolve_context(request: GatewayRequest) -> GatewayResponse`

**설명**: 슬롯을 입력받아 5개 Resolver를 실행하고, context 번들을 조합하여 반환합니다.

**실행 순서**:
1. Source Resolver → `source_context`
2. Route Resolver → `route_context`
3. Procedure Resolver → `procedure_context`
4. Item Resolver → `item_eligibility_context`
5. Company Resolver → `company_candidate_context`

**특성**:
- read-only. DB write 없음.
- 외부 API 호출 없음.
- LLM 호출 없음.
- 판단 없음. 조회 결과만 반환.

---

## 3. 입력 모델: GatewayRequest

```python
@dataclass
class GatewayRequest:
    request_id: str                  # UUID
    user_query: str                  # 사용자 질문 원문
    slots: SlotValues                # 추출된 슬롯

@dataclass
class SlotValues:
    buyer_type: Optional[str]        # "local_government" | "national_government" | "public_institution" | None
    contract_object: Optional[str]   # "construction" | "goods" | "service" | None
    amount: Optional[int]            # 추정가격 (원) | None
    procurement_route: Optional[str] # "pps_delegated_contract" | "mas" | "pps_shopping_mall" | ... | None
    contract_method: Optional[str]   # "general_competition" | "limited_competition" | "direct_contract" | ... | None
    item_name: Optional[str]         # 품목명 (일반명) | None
    detail_item_code: Optional[str]  # 세부품명번호 | None
    company_id: Optional[str]        # 특정 업체 ID | None
    location: str = "부산"            # 지역 (기본값: 부산)
```

### 슬롯 유효값

| 슬롯 | 유효값 | 필수 |
|------|--------|:----:|
| `buyer_type` | `local_government`, `national_government`, `public_institution` | ❌ (null 허용, assumed 처리) |
| `contract_object` | `construction`, `goods`, `service` | ❌ |
| `amount` | 양의 정수 (원 단위) | ❌ |
| `procurement_route` | `pps_delegated_contract`, `pps_central_procurement`, `pps_shopping_mall`, `mas`, `third_party_unit_price_contract`, `catalog_contract`, `pps_facility_work`, `pps_technical_service` | ❌ |
| `contract_method` | `general_competition`, `limited_competition`, `designated_competition`, `direct_contract` | ❌ |
| `item_name` | 자유 텍스트 | ❌ |
| `detail_item_code` | 숫자 문자열 (예: "4617162201") | ❌ |
| `company_id` | HMAC-SHA256 해시 | ❌ |
| `location` | 지역명 | ✅ (기본: "부산") |

---

## 4. 출력 모델: GatewayResponse

```python
@dataclass
class GatewayResponse:
    request_id: str
    gateway_version: str = "v0.1.1"
    baseline_db: str = "legal_db_v0_1_3.sqlite"
    source_context: SourceContext
    route_context: RouteContext
    procedure_context: ProcedureContext
    item_eligibility_result: ItemEligibilityResult    # 항상 존재. resolver_status로 상태 구분
    company_candidate_context: Optional[CompanyCandidateContext]  # 검색 조건 없으면 null
    metadata: GatewayMetadata
    error: Optional[str] = None              # 정상이면 null
```

---

## 5. Resolver별 API 상세

### 5.1 Source Resolver

```python
def resolve_sources(
    buyer_type: Optional[str],
    contract_object: Optional[str]
) -> SourceContext
```

**반환**:
```python
@dataclass
class SourceContext:
    sources: List[SourceEntry]
    assumed_buyer_type: Optional[str]       # buyer_type 미제공 시 "local_government"
    assumption_reason: Optional[str]        # "부산시 업무 기본 맥락에 따른 임시 추정"
    buyer_type_confidence: Optional[str]    # "low" | "high" | None
    required_slots_missing: List[str]       # ["buyer_type"] 등

@dataclass
class SourceEntry:
    source_id: str
    source_name: str
    normalized_title: str
    law_category: Optional[str]
    source_type: Optional[str]
    applicability_scope: Optional[str]
    active_for_rule: bool                   # 항상 True (source_context에 포함되는 조건)
    activation_mode: Optional[str]
```

**buyer_type 분기**:

| buyer_type 입력 | 동작 |
|----------------|------|
| `"local_government"` | local_contract jurisdiction source 조회. confidence = "high" |
| `"national_government"` | national_contract jurisdiction source 조회. confidence = "high" |
| `"public_institution"` | public_institution_contract jurisdiction source 조회. confidence = "high" |
| `null` | local_contract jurisdiction source 조회. assumed_buyer_type = "local_government", confidence = "low", required_slots_missing = ["buyer_type"] |

### 5.2 Route Resolver

```python
def resolve_route(
    buyer_type: Optional[str],
    procurement_route: Optional[str]
) -> RouteContext
```

**반환**:
```python
@dataclass
class RouteContext:
    base_jurisdiction: str                  # "local_contract" 등
    overlay_applied: bool
    overlay_scope: Optional[str]            # "pps_delegated_contract" 등
    overlay_sources: List[SourceEntry]      # 조달청 기준 (overlay 시에만 채워짐)
    dual_routing: bool                      # True면 source_context의 base + overlay 병합
```

> **[설계 원칙] base source 중복 조회 제거**:  
> base source 조회는 **Source Resolver 전담**입니다.  
> Route Resolver는 overlay 여부 판정과 overlay source 조회만 수행합니다.  
> Rule Engine은 `source_context.sources`(base) + `route_context.overlay_sources`(overlay)를 병합하여 사용합니다.  
> 이렇게 하면 base source 불일치 가능성이 제거됩니다.

**procurement_route 분기**:

| procurement_route 입력 | 동작 |
|----------------------|------|
| `null` | overlay_applied = false. overlay_sources = [] |
| 조달청 경로 값 | overlay_applied = true. overlay_sources 조회 |

### 5.3 Procedure Resolver

```python
def resolve_procedures(
    buyer_type: Optional[str],
    contract_object: Optional[str],
    procurement_route: Optional[str],
    contract_method: Optional[str],
    procedure_topic: Optional[str]          # "위원회구성" | "물가변동" | "제안서평가" | ... | None
) -> ProcedureContext
```

**반환**:
```python
@dataclass
class ProcedureContext:
    sources: List[ProcedureSourceEntry]
    filter_applied: bool                    # 필터가 적용되었는지 여부
    usage: str = "answer_builder_procedure_section_only"
    judgment_eligible: bool = False         # 항상 False

@dataclass
class ProcedureSourceEntry:
    source_id: str
    source_name: str
    source_type: Optional[str]
    applicability_scope: Optional[str]      # 절차 source의 적용 범위
    usage: str = "procedure_guidance_only"
```

**필터 동작**:
- procedure_only source 전체를 무조건 반환하지 않습니다.
- buyer_type, contract_object, procurement_route, contract_method, procedure_topic으로 필터링하여 **관련 절차 source만** 반환합니다.
- 모든 필터가 null이면 해당 조건의 절차 source를 넓게 반환합니다 (전체 반환은 아님).

| 필터 | 예시 | 동작 |
|------|------|------|
| `contract_object = "construction"` | 공사 절차만 | 공사 관련 절차 source만 반환 |
| `procedure_topic = "물가변동"` | 물가변동 처리 절차 | 해당 topic 관련 source만 반환 |
| `buyer_type = "local_government"` | 지방자치단체 절차 | 지방계약 관련 절차 source만 반환 |

**제약**:
- `active_for_procedure = 1` AND `active_for_rule = 0` source만 조회.
- Rule Engine 판단 근거로 사용 **금지**. Answer Builder 절차 안내 섹션에서만 사용.
- procedure_context 결과로 계약 방식, 낙찰자 결정 가능 여부를 확정하지 않음.

### 5.4 Item Resolver

```python
def resolve_item_eligibility(
    user_query: str,
    item_name: Optional[str],
    detail_item_code: Optional[str],
    company_id: Optional[str],
    procurement_route: Optional[str],
    contract_method: Optional[str]
) -> ItemEligibilityResult
```

**반환** (항상 반환. null이 아닌 resolver_status로 상태 구분):
```python
@dataclass
class ItemEligibilityResult:
    resolver_status: str                    # "resolved" | "not_triggered" | "data_unavailable" | "ambiguous"
    unavailable_reason: Optional[str]       # 상세 사유 (data_unavailable 시)
    context: Optional[ItemEligibilityContext]  # resolved 시에만 채워짐

@dataclass
class ItemEligibilityContext:
    item_eligibility_required: bool = True
    trigger_grade: str                      # "explicit" | "silent"
    triggered_by: List[str]                 # ["T1_keyword", "T2_detail_item_code", ...]
    detail_item_resolved: bool
    detail_item_code: Optional[str]
    detail_item_name: Optional[str]
    detail_item_candidates: Optional[List[dict]]  # 복수 후보 시
    is_sme_competition_product: Optional[bool]
    direct_production_required: Optional[bool]
    company_cert_status: Optional[str]      # "valid" | "expired" | "unknown" | None
    eligibility_status: Optional[str]       # item_eligibility_status_taxonomy.json 값
    candidate_action: Optional[str]         # item_eligibility_status_taxonomy.json 값
```

**resolver_status 값 정의**:

| 값 | 의미 | context | Rule Engine 해석 |
|:---|------|:-------:|------------------|
| `resolved` | 트리거 발동 + 데이터 조회 완료 | 채워짐 | eligibility_context 소비 |
| `not_triggered` | 트리거 미발동 (검토 불필요) | null | ❽ 완전 스킵 |
| `data_unavailable` | 트리거 발동했으나 조회 데이터 부족 | null | "데이터 확인 필요" 안내 가능 |
| `ambiguous` | 트리거 발동 + 복수 후보, 세부품명 미확정 | 부분 채움 | 세부품명 확정 유도 |

**unavailable_reason 값 예시**:
- `item_alias_map_not_available`: alias_map 테이블 미구축
- `sme_competition_table_not_available`: 중기경쟁제품 테이블 미구축
- `company_cert_table_not_available`: 직생 인증 매핑 테이블 미구축
- `detail_item_code_ambiguous`: 복수 세부품명 후보, 확정 불가

**트리거 판정 순서** (`item_eligibility_trigger_policy_v0_1_4.md` 기준):

| 순서 | 조건 | 결과 |
|:----:|------|------|
| 1 | T1: user_query에 트리거 키워드 포함 | trigger_grade = "explicit" |
| 2 | T2: detail_item_code 제공 | trigger_grade = "explicit" |
| 3 | T5: 계약경로상 중기경쟁 검증 필수 | trigger_grade = "explicit" |
| 4 | T3: item_alias_map 해소 결과 중기경쟁 후보 | trigger_grade = "silent" |
| 5 | 모두 미충족 | resolver_status = "not_triggered" |

### 5.5 Company Resolver

```python
def resolve_company_candidates(
    item_name: Optional[str],
    location: str,
    company_id: Optional[str],
    detail_item_code: Optional[str],
    detail_item_candidates: Optional[List[str]]
) -> Optional[CompanyCandidateContext]
```

**반환** (검색 조건 없으면 `None`):
```python
@dataclass
class CompanyCandidateContext:
    candidates: List[CompanyCandidate]
    enrichment_applied: bool
    enrichment_scope: Optional[str]         # "specific_item" | "candidate_items" | "general"
    total_found: int

@dataclass
class CompanyCandidate:
    company_id: str                         # HMAC-SHA256 해시
    company_name_masked: str                # 부분 마스킹
    location: str
    business_type: Optional[str]
    contract_count: Optional[int]
    contract_amount: Optional[int]
    enrichment_data: Optional[EnrichmentData]

@dataclass
class EnrichmentData:
    cert_status: Optional[str]              # "valid" | "expired" | None
    cert_expiry: Optional[str]              # "YYYY-MM" | None
    detail_item_codes: Optional[List[str]]  # 직생 보유 세부품명 목록
    matched_by: Optional[str]               # "specific_code" | "candidate_match" | "company_level"
    per_candidate_match: Optional[List[dict]]  # 복수 후보 시 후보별 매칭 결과
```

**T4 Enrichment 동작**:
- 후보 업체 조회 완료 후 각 업체에 대해 `company_direct_production_cert_mapping` 조회.
- 직생 데이터 있으면 `enrichment_data` 첨부. 없으면 `null`.
- Enrichment 결과는 계약 판단에 **영향 없음**. 후보표 optional column 용도.

**세부품명 기반 Enrichment 분기**:

| detail_item_code | detail_item_candidates | 동작 | enrichment_scope |
|:----------------:|:---------------------:|------|:----------------:|
| 확정값 있음 | 무관 | 해당 세부품명 기준으로 직생 조회 | `specific_item` |
| null | 후보 있음 | 후보 세부품명별 직생 보유 여부를 `per_candidate_match`에 배열로 표시 | `candidate_items` |
| null | null | 업체 수준의 직생 데이터만 조회. 세부품명 기준 매칭 불가 | `general` |

**세부품명 정보 없을 때 제약**:
- `enrichment_scope = "general"`이면 직생을 **단정적으로 표시하지 않음**.
- 후보표에는 "직생 데이터 있음 (세부품명 미확정)" 수준의 참고 정보만 표시.
- `matched_by = "company_level"`로 명시하여, 세부품명 기준 매칭이 아님을 구분.

---

## 6. 메타데이터 모델

```python
@dataclass
class GatewayMetadata:
    total_sources_matched: int
    procedure_sources_matched: int
    overlay_applied: bool
    item_eligibility_resolver_status: str    # "resolved" | "not_triggered" | "data_unavailable" | "ambiguous"
    item_eligibility_trigger_grade: Optional[str]  # "explicit" | "silent" | None
    company_candidates_found: int
    enrichment_applied: bool
    enrichment_scope: Optional[str]          # "specific_item" | "candidate_items" | "general" | None
```

---

## 7. 에러 모델

Gateway는 에러 발생 시에도 **부분 context를 반환**합니다. 전체 실패만 error 필드에 기록합니다.

```python
# 정상 (전체 성공)
GatewayResponse(
    source_context=SourceContext(...),
    route_context=RouteContext(...),
    ...
    error=None
)

# 부분 실패 (업체 DB만 실패)
GatewayResponse(
    source_context=SourceContext(...),    # 정상
    route_context=RouteContext(...),      # 정상
    company_candidate_context=None,       # 실패
    error="company_db_connection_failed: Connection refused"
)
```

---

## 8. 사용 예시

### 예시 1: 일반 금액 질문

```python
request = GatewayRequest(
    request_id="550e8400-e29b-41d4-a716-446655440000",
    user_query="8천만원 물품 수의계약 가능한가?",
    slots=SlotValues(
        buyer_type=None,                # 미제공
        contract_object="goods",
        amount=80_000_000,
        contract_method="direct_contract"
    )
)

response = resolve_context(request)
# response.source_context.assumed_buyer_type = "local_government"
# response.source_context.buyer_type_confidence = "low"
# response.source_context.required_slots_missing = ["buyer_type"]
# response.item_eligibility_result.resolver_status == "not_triggered"  (트리거 미발동)
# response.item_eligibility_result.context is None
# response.company_candidate_context is None (업체 검색 없음)
```

### 예시 2: 직생 명시 + 업체 검색

```python
request = GatewayRequest(
    request_id="550e8400-e29b-41d4-a716-446655440001",
    user_query="CCTV 부산업체 찾아줘. 직생도 봐줘.",
    slots=SlotValues(
        item_name="CCTV",
        location="부산"
    )
)

response = resolve_context(request)
# response.item_eligibility_result.resolver_status == "resolved"
# response.item_eligibility_result.context.trigger_grade == "explicit"
# response.item_eligibility_result.context.triggered_by == ["T1_keyword"]
# response.company_candidate_context.candidates = [...]
# response.company_candidate_context.enrichment_applied == True
```

### 예시 3: 일반 품목명 (Silent)

```python
request = GatewayRequest(
    request_id="550e8400-e29b-41d4-a716-446655440002",
    user_query="컴퓨터 구매 방법 알려줘",
    slots=SlotValues(
        item_name="컴퓨터",
        contract_object="goods"
    )
)

response = resolve_context(request)
# response.item_eligibility_result.resolver_status == "resolved"
# response.item_eligibility_result.context.trigger_grade == "silent"
# response.item_eligibility_result.context.triggered_by == ["T3_alias_map_sme_candidate"]
# → Rule Engine: 내부 분류만
# → Answer Builder: 보조 문구 1줄만
```

---

## 9. Gateway가 생성하지 않는 것

| 항목 | Gateway | Answer Builder | 비고 |
|------|:-------:|:--------------:|------|
| 수의계약 검토 경로 안내 | ❌ | ✅ (검토 안내만, 단정 금지) | "수의계약 가능합니다" 단정 표현 금지 |
| 지역제한 적용 가능성 검토 안내 | ❌ | ✅ (검토 안내만, 단정 금지) | "지역제한 가능합니다" 단정 표현 금지 |
| decision_context 기반 검토 결과 | ❌ | ✅ (검토 결과 안내) | 법적 결론이 아닌 검토 경로 안내 |
| 자연어 답변 | ❌ | ✅ | |
| DB INSERT/UPDATE/DELETE | ❌ | ❌ | 전체 시스템 금지 |
| 외부 API 호출 | ❌ | ❌ | 전체 시스템 금지 |

> **[금지 표현 원칙]**  
> Answer Builder도 다음 **단정 표현을 생성하지 않습니다**:  
> - "계약 가능합니다", "구매 가능합니다", "수의계약 가능합니다"  
> - "지역제한 가능합니다", "낙찰 가능합니다"  
> Answer Builder는 "검토 경로", "적용 가능성", "확인 필요" 수준의 안내만 생성합니다.  
> 최종 계약 가능 여부는 실무 담당자가 판단합니다.
