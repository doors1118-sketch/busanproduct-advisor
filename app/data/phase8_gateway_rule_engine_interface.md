# Phase 8 Gateway → Rule Engine Interface

> **버전**: v0.1.1  
> **기준**: `phase8_gateway_api_spec.md` v0.1.1, `phase8_gateway_response_schema.json` v0.1.1  
> **준수**: `phase7_no_mutation_policy.md` (A9)

---

## 1. 개요

본 문서는 Gateway가 출력한 `GatewayResponse`를 Rule Engine이 소비하는 인터페이스를 정의합니다.

```
Gateway                    Rule Engine                 Answer Builder
GatewayResponse ──────────▶ rule evaluation ──────────▶ 자연어 답변
(context 번들)              (decision context)          (trigger_grade별 노출)
```

**원칙**:
- Rule Engine은 `GatewayResponse`의 **구조화된 필드만** 소비합니다.
- Rule Engine은 자연어 답변을 생성하지 않습니다.
- Rule Engine은 DB를 수정하지 않습니다.

---

## 2. Rule Engine 입력 매핑

### 2.1 필수 소비 필드

Rule Engine은 `GatewayResponse`에서 다음 필드를 **항상** 읽습니다:

| GatewayResponse 필드 | Rule Engine 소비 | 용도 |
|---------------------|:-:|------|
| `source_context.sources` | ✅ | ❶~❼ 판단 근거 법령 |
| `source_context.buyer_type_confidence` | ✅ | 기관유형 확정 여부 판단 |
| `source_context.required_slots_missing` | ✅ | 추가 질문 유도 판단 |
| `route_context.overlay_applied` | ✅ | overlay 적용 여부 |
| `route_context.overlay_sources` | ✅ | overlay 법령 (병합 대상) |
| `route_context.dual_routing` | ✅ | base+overlay 병합 여부 |
| `item_eligibility_result.resolver_status` | ✅ | ❽ 실행 여부 판단 |
| `metadata` | ✅ | 요약 정보 |
| `error` | ✅ | 에러 시 fallback 판단 |

### 2.2 조건부 소비 필드

| GatewayResponse 필드 | 소비 조건 | 용도 |
|---------------------|----------|------|
| `item_eligibility_result.context` | resolver_status ∈ {resolved, ambiguous} | ❽ eligibility 판단 |
| `item_eligibility_result.context.trigger_grade` | context ≠ null | Answer Builder 노출 수준 결정 |
| `company_candidate_context` | ≠ null | 업체 후보 처리 |

### 2.3 소비하지 않는 필드

| GatewayResponse 필드 | Rule Engine | 사유 |
|---------------------|:-:|------|
| `procedure_context` | ❌ | Answer Builder 전용. judgment_eligible=false |
| `gateway_version` | ❌ | 디버깅용 |
| `baseline_db` | ❌ | 디버깅용 |

---

## 3. Rule Engine 8단계 매핑

### ❶ buyer_type 판단

```
입력: source_context.buyer_type_confidence
      source_context.required_slots_missing

if buyer_type_confidence == "low":
    → 추가 질문 유도 (Answer Builder에 전달)
    → 판단은 assumed 기준으로 임시 진행
elif buyer_type_confidence == "high":
    → 확정된 buyer_type 기준으로 판단
```

### ❷ contract_object 판단

```
입력: slots.contract_object (GatewayRequest에서 전달)

→ 공사/물품/용역 분기
→ source_context.sources에서 해당 contract_object 관련 source 필터링
```

### ❸ amount 판단

```
입력: slots.amount

→ 금액 기준 계약방식 분기 (수의계약 한도 등)
→ source_context.sources에서 금액 관련 조문 참조
```

### ❹ procurement_route 판단

```
입력: route_context.overlay_applied
      route_context.overlay_sources
      route_context.dual_routing

if overlay_applied:
    applicable_sources = source_context.sources + route_context.overlay_sources
else:
    applicable_sources = source_context.sources
```

### ❺ contract_method 판단

```
입력: slots.contract_method

→ 일반경쟁/제한경쟁/지명경쟁/수의계약 분기
→ applicable_sources에서 해당 계약방식 관련 조문 참조
```

### ❻ local_preference 판단

```
입력: slots.amount, slots.contract_object, slots.location

→ 지역제한 적용 가능성 검토
→ 지역제한 관련 source 참조
```

### ❼ policy_company / certification 판단

```
입력: slots (정책기업, 인증 관련 슬롯)

→ 중소기업, 여성기업, 사회적기업 등 정책 우대 검토
→ overlay_scope에서 sme_purchase, policy_company 등 확인
```

### ❽ item_eligibility 판단

```
입력: item_eligibility_result.resolver_status
      item_eligibility_result.context (있으면)

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

---

## 4. Rule Engine 출력: DecisionContext

Rule Engine은 판단 결과를 `DecisionContext`로 Answer Builder에 전달합니다.

```python
@dataclass
class DecisionContext:
    buyer_type_confirmed: bool
    buyer_type_assumed: Optional[str]
    slots_missing: List[str]
    applicable_sources: List[str]       # source_id 목록
    contract_method_candidates: List[str]
    amount_threshold_met: Optional[bool]
    local_preference_applicable: Optional[bool]
    item_eligibility_grade: Optional[str]  # "explicit" | "silent" | None
    item_eligibility_status: Optional[str]
    enrichment_available: bool
    decision_notes: List[str]           # 판단 근거 요약
```

---

## 5. Answer Builder 소비 규칙

Answer Builder는 `DecisionContext` + `GatewayResponse`의 일부를 소비합니다.

| 소스 | 필드 | 용도 |
|------|------|------|
| DecisionContext | 전체 | 판단 결과 기반 답변 생성 |
| GatewayResponse | `procedure_context` | 절차 안내 섹션 (judgment_eligible=false) |
| GatewayResponse | `company_candidate_context` | 후보 업체 표 |
| GatewayResponse | `item_eligibility_result.context.trigger_grade` | 노출 수준 결정 |

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
| `buyer_type_confidence = "low"` | 임시 판단 + 추가 질문 유도 |

---

## 7. 데이터 흐름 요약

```
GatewayResponse
    │
    ├── source_context.sources ──────────────▶ ❶~❼ 판단 근거
    ├── source_context.buyer_type_confidence ─▶ ❶ 기관유형 확정 여부
    ├── route_context.overlay_sources ────────▶ ❹ overlay 병합
    ├── item_eligibility_result ─────────────▶ ❽ 트리거/등급 판단
    │
    ▼
DecisionContext
    │
    ├── 판단 결과 ──────────────────────────▶ Answer Builder
    │
    ▼
GatewayResponse (Answer Builder 직접 참조)
    ├── procedure_context ───────────────────▶ 절차 안내 섹션
    ├── company_candidate_context ───────────▶ 후보 업체 표
    └── item_eligibility_result.context ─────▶ trigger_grade별 노출
```
