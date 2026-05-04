# Phase 8 Gateway → Rule Engine Interface

> **버전**: v0.1.1  
> **기준**: `phase8_gateway_api_spec.md` v0.1.1, `phase8_gateway_response_schema.json` v0.1.1  
> **준수**: `phase7_no_mutation_policy.md` (A9)

---

## 1. 개요

본 문서는 Gateway가 출력한 `GatewayResponse`와 원본 슬롯(`GatewayRequest`)을 Rule Engine이 소비하는 인터페이스를 정의합니다.

```
Slot Parser     Gateway              Rule Engine           Answer Builder
GatewayRequest ─▶ GatewayResponse ─┐
                                   ├─▶ rule evaluation ──▶ 자연어 답변
GatewayRequest (slots) ────────────┘   (decision context)  (trigger_grade별 노출)
```

### 1.1 Rule Engine 입력 객체

Rule Engine은 `GatewayResponse`만이 아니라 원본 슬롯도 필요합니다.

```python
@dataclass
class RuleEngineInput:
    original_request: GatewayRequest      # 원본 슬롯 포함
    gateway_response: GatewayResponse     # Gateway 조회 결과
```

> **[설계 사유]** GatewayResponse에는 slots가 포함되어 있지 않습니다.  
> ❷~❼ 단계에서 `contract_object`, `amount`, `contract_method`, `location` 등  
> 슬롯 값이 필요하므로 `original_request`를 함께 전달합니다.

**원칙**:
- Rule Engine은 `RuleEngineInput`의 **구조화된 필드만** 소비합니다.
- Rule Engine은 자연어 답변을 생성하지 않습니다.
- Rule Engine은 DB를 수정하지 않습니다.
- Enrichment 데이터는 계약 판단에 **영향을 주지 않습니다**.

---

## 2. Rule Engine 입력 매핑

### 2.1 필수 소비 필드 — original_request.slots

| 필드 | 사용 단계 | 용도 |
|------|:--------:|------|
| `slots.buyer_type` | ❶ | 기관유형 분기 |
| `slots.contract_object` | ❷ | 공사/물품/용역 분기 |
| `slots.amount` | ❸ ❻ | 금액 기준 분기, 지역제한 금액 요건 |
| `slots.procurement_route` | ❹ | 조달경로 분기 |
| `slots.contract_method` | ❺ | 계약방식 분기 |
| `slots.item_name` | ❽ | Item Resolver 결과 해석 보조 |
| `slots.detail_item_code` | ❽ | 세부품명 확정 여부 확인 보조 |
| `slots.location` | ❻ | 지역제한 적용 범위 |

> **[Item Eligibility 판정 원칙]**  
> Item Eligibility 트리거 판정은 Gateway의 Item Resolver가 수행합니다.  
> Rule Engine은 `item_eligibility_result.resolver_status`와 `context.trigger_grade`를 해석할 뿐, T1/T2/T3/T5를 재판정하지 않습니다.

### 2.2 필수 소비 필드 — gateway_response

| GatewayResponse 필드 | 사용 단계 | 용도 |
|---------------------|:--------:|------|
| `source_context.sources` | ❶~❼ | 판단 근거 법령 |
| `source_context.buyer_type_confidence` | ❶ | 기관유형 확정 여부 |
| `source_context.required_slots_missing` | ❶ | 추가 질문 유도 |
| `route_context.overlay_applied` | ❹ | overlay 적용 여부 |
| `route_context.overlay_sources` | ❹ | overlay 법령 (병합) |
| `route_context.dual_routing` | ❹ | base+overlay 병합 여부 |
| `item_eligibility_result.resolver_status` | ❽ | 실행 여부 판단 |
| `metadata` | 전체 | 요약 정보 |
| `error` | 전체 | 에러 시 fallback |

### 2.3 조건부 소비 필드

| GatewayResponse 필드 | 소비 조건 | 용도 |
|---------------------|----------|------|
| `item_eligibility_result.context` | resolver_status ∈ {resolved, ambiguous} | ❽ eligibility 판단 |
| `item_eligibility_result.context.trigger_grade` | context ≠ null | Answer Builder 노출 수준 결정 |
| `company_candidate_context` | ≠ null | 업체 후보 처리 |

### 2.4 소비하지 않는 필드

| GatewayResponse 필드 | Rule Engine | 사유 |
|---------------------|:-:|------|
| `procedure_context` | ❌ | Answer Builder 전용. judgment_eligible=false |
| `gateway_version` | ❌ | 디버깅용 |
| `baseline_db` | ❌ | 디버깅용 |

---

## 3. Rule Engine 8단계 매핑

### ❶ buyer_type 판단

```
입력: original_request.slots.buyer_type
      gateway_response.source_context.buyer_type_confidence
      gateway_response.source_context.required_slots_missing

if buyer_type_confidence == "low":
    → provisional_evaluation = true
    → assumption_warnings에 "기관유형 미확정. 부산시 기준 임시 추정." 추가
    → 판단은 assumed 기준으로 임시 진행하되 provisional 플래그 전달
elif buyer_type_confidence == "high":
    → provisional_evaluation = false
    → 확정된 buyer_type 기준으로 판단
```

### ❷ contract_object 판단

```
입력: original_request.slots.contract_object

→ 공사/물품/용역 분기
→ gateway_response.source_context.sources에서 해당 contract_object 관련 source 필터링
```

### ❸ amount 판단

```
입력: original_request.slots.amount

→ 금액 기준 계약방식 분기 (수의계약 한도 등)
→ applicable_sources에서 금액 관련 조문 참조
```

### ❹ procurement_route 판단

```
입력: gateway_response.route_context.overlay_applied
      gateway_response.route_context.overlay_sources
      gateway_response.route_context.dual_routing

if overlay_applied:
    applicable_sources = gateway_response.source_context.sources
                       + gateway_response.route_context.overlay_sources
else:
    applicable_sources = gateway_response.source_context.sources
```

### ❺ contract_method 판단

```
입력: original_request.slots.contract_method

→ 일반경쟁/제한경쟁/지명경쟁/수의계약 분기
→ applicable_sources에서 해당 계약방식 관련 조문 참조
```

### ❻ local_preference 판단

```
입력: original_request.slots.amount
      original_request.slots.contract_object
      original_request.slots.location

→ 지역제한 적용 가능성 검토
→ applicable_sources에서 지역제한 관련 조문 참조
```

### ❼ policy_company / certification 판단

```
입력: original_request.slots (정책기업, 인증 관련 슬롯)
      gateway_response.route_context.overlay_scope

→ 중소기업, 여성기업, 사회적기업 등 정책 우대 검토
→ overlay_scope에서 sme_purchase, policy_company 등 확인
```

### ❽ item_eligibility 판단

```
입력: gateway_response.item_eligibility_result.resolver_status
      gateway_response.item_eligibility_result.context (있으면)

switch resolver_status:
  case "not_triggered":
    → ❽ 완전 스킵

  case "resolved":
    grade = context.trigger_grade
    if grade == "explicit":
      → Rule Engine: eligibility 전면 평가
      → Answer Builder: 별도 섹션 표시
    elif grade == "silent":
      → Rule Engine: 내부 분류만
      → Answer Builder: 보조 문구 1줄

  case "data_unavailable":
    → Rule Engine: ❽ 스킵
    → Answer Builder: "데이터 확인 필요" 안내 가능

  case "ambiguous":
    → Rule Engine: partial context 참조 (후보 목록)
    → Answer Builder: 세부품명 확정 유도 문구
```

> **[Enrichment 판단 영향 금지]**  
> `company_candidate_context.enrichment_data`는 후보표 보조 정보입니다.  
> `enrichment_available = true`여도 다음 필드를 **변경하지 않습니다**:  
> - `contract_method_candidates`  
> - `amount_threshold_met`  
> - `local_preference_applicable`  
> 직생 유효 여부는 계약 가능 판단으로 연결하지 않습니다.

---

## 4. Rule Engine 출력: DecisionContext

Rule Engine은 판단 결과를 `DecisionContext`로 Answer Builder에 전달합니다.

```python
@dataclass
class DecisionContext:
    # ❶ 기관유형
    buyer_type_confirmed: bool
    buyer_type_assumed: Optional[str]
    provisional_evaluation: bool             # buyer_type 미확정 시 True
    assumption_warnings: List[str]           # ["기관유형 미확정. 부산시 기준 임시 추정."] 등
    slots_missing: List[str]

    # ❷~❼ 판단 결과
    applicable_sources: List[str]            # source_id 목록
    contract_method_candidates: List[str]
    amount_threshold_met: Optional[bool]
    local_preference_applicable: Optional[bool]

    # ❽ Item Eligibility
    item_eligibility_grade: Optional[str]    # "explicit" | "silent" | None
    item_eligibility_status: Optional[str]

    # Enrichment (판단 영향 없음)
    enrichment_available: bool
    enrichment_judgment_effect: str = "none" # 항상 "none". 판단에 영향 없음 명시.

    # 판단 근거
    decision_notes: List[str]
```

> **`enrichment_judgment_effect = "none"`**: Enrichment 데이터가 존재하더라도  
> 계약방식·금액기준·지역제한 등 ❶~❼ 판단 결과를 변경하지 않습니다.  
> 이 필드는 이 원칙을 코드 수준에서 명시하기 위한 것입니다.

---

## 5. Answer Builder 소비 규칙

Answer Builder는 `DecisionContext` + `GatewayResponse`의 일부를 소비합니다.

| 소스 | 필드 | 용도 |
|------|------|------|
| DecisionContext | 전체 | 판단 결과 기반 답변 생성 |
| DecisionContext | `item_eligibility_grade` | 노출 수준 1차 결정 (우선 참조) |
| GatewayResponse | `procedure_context` | 절차 안내 섹션 (judgment_eligible=false) |
| GatewayResponse | `company_candidate_context` | 후보 업체 표 |
| GatewayResponse | `item_eligibility_result.context` | 상세 상태 표시 (context ≠ null일 때만) |

> **[trigger_grade 참조 원칙]**  
> Answer Builder는 노출 수준 결정 시 `DecisionContext.item_eligibility_grade`를 **우선 사용**합니다.  
> `GatewayResponse.item_eligibility_result.context`는 `context`가 `null`이 아닐 때만 세부 상태 표시에 활용하며, `not_triggered`나 `data_unavailable` 상태에서 `context.trigger_grade`를 직접 참조하지 않습니다.

### trigger_grade별 Answer Builder 동작

| trigger_grade | 직생 섹션 | 후보표 직생 열 | 보조 문구 |
|:---:|:---:|:---:|:---:|
| explicit | ✅ 별도 섹션 | ✅ 정규 열 | — |
| silent | ❌ | ❌ | ✅ 1줄 |
| null (미발동) | ❌ | ❌ | ❌ |

### 금지 표현

Answer Builder는 다음 단정 표현을 생성하지 않습니다:
- "계약 가능합니다", "구매 가능합니다", "수의계약 가능합니다"
- "지역제한 가능합니다", "낙찰 가능합니다"

허용 표현:
- "검토 경로", "적용 가능성", "확인 필요"

---

## 6. 에러 처리 인터페이스

| GatewayResponse 상태 | Rule Engine 동작 |
|---------------------|-----------------|
| `error = null` | 정상 실행 |
| `error ≠ null` + 부분 context 존재 | 가용 context로 판단, 에러 부분은 "확인 불가" |
| `source_context.sources = []` | "관련 법령 미발견" → Answer Builder에 전달 |
| `buyer_type_confidence = "low"` | provisional_evaluation=true + assumption_warnings 생성 + 추가 질문 유도 |

---

## 7. 데이터 흐름 요약

```
RuleEngineInput
    ├── original_request.slots ──────────────▶ ❷~❼ 슬롯 기반 분기
    │
    └── gateway_response
        ├── source_context.sources ──────────▶ ❶~❼ 판단 근거
        ├── source_context.buyer_type_confidence ▶ ❶ 기관유형 확정
        ├── route_context.overlay_sources ───▶ ❹ overlay 병합
        ├── item_eligibility_result ─────────▶ ❽ 트리거/등급
        │
        ▼
    DecisionContext (enrichment_judgment_effect = "none")
        │
        ├── 판단 결과 ──────────────────────▶ Answer Builder
        │
        ▼
    gateway_response (Answer Builder 직접 참조)
        ├── procedure_context ──────────────▶ 절차 안내 섹션
        ├── company_candidate_context ──────▶ 후보 업체 표
        └── item_eligibility_result.context ▶ trigger_grade별 노출
```
