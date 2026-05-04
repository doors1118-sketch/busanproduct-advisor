# Item Eligibility Trigger Policy v0.1.4

본 문서는 Rule Engine에서 Item Eligibility 레이어를 호출하는 **트리거 조건**을 정의합니다.
v0.1.3 대비 변경: T3를 silent trigger로 분류, T4를 enrichment trigger로 분리.

## 1. 핵심 원칙

- 직접생산확인은 **전체 계약판단의 공통 게이트가 아닙니다**.
- 직접생산확인은 **중소기업자간 경쟁제품으로 특정되거나, 사용자가 직생/중기경쟁제품을 명시한 경우**에만 작동하는 조건부 레이어입니다.
- `item_eligibility_required = false`이면 Item Eligibility 레이어는 **완전 스킵**됩니다.

## 2. 트리거 분류 체계

v0.1.4에서 트리거를 3가지 등급으로 분류합니다.

| 등급 | 명칭 | 답변 노출 수준 | 후보표 직생 열 |
|:----:|------|:--------------:|:--------------:|
| **Explicit** | 사용자가 직생/중기경쟁을 직접 언급 | 전면 노출 (별도 섹션) | 전면 표시 |
| **Silent** | 시스템이 내부적으로 중기경쟁 후보를 감지 | 보조 문구만 (1줄) | 비표시 |
| **Enrichment** | 업체 후보 조회 후 직생 데이터 발견 | 보조 열 표시만 | optional column |

## 3. 트리거 조건 상세

### Explicit Triggers (전면 노출)

| # | 조건 | 판정 기준 | 등급 |
|:-:|------|-----------|:----:|
| T1 | **사용자 질의에 직생/중기경쟁 키워드 포함** | `user_query`에 트리거 키워드 포함 | Explicit |
| T2 | **세부품명번호가 명시적으로 제공됨** | `detail_item_code`가 사용자 입력 또는 이전 대화에서 확정됨 | Explicit |
| T5 | **계약경로상 중기경쟁제품 검증이 필수** | `procurement_route`/`contract_method` 판정 결과 중기경쟁입찰 적용 경로 | Explicit |

### Silent Trigger (내부 분류 전용)

| # | 조건 | 판정 기준 | 등급 |
|:-:|------|-----------|:----:|
| T3 | **item_alias_map이 중기경쟁제품 후보로 해소됨** | 매칭된 세부품명 후보 중 하나 이상이 `is_sme_competition_product = true` | **Silent** |

### Enrichment Trigger (후보표 보조 정보)

| # | 조건 | 판정 기준 | 등급 |
|:-:|------|-----------|:----:|
| T4 | **후보 업체에 직접생산확인 데이터가 존재** | `company_direct_production_cert_mapping`에 인증 데이터 1건 이상 존재 | **Enrichment** |

## 4. 트리거 판정 흐름도

```
사용자 질문 입력
    │
    ▼
[키워드 스캔] user_query에 직생/중기경쟁 키워드 있는가?
    ├─ Yes ──→ item_eligibility_required = true (Explicit)
    │          → 답변에 직생/중기경쟁 섹션 전면 표시
    │          → 후보표에 직생 상태 열 전면 표시
    │
    ▼ No
[세부품명 확인] detail_item_code가 제공되었는가?
    ├─ Yes ──→ item_eligibility_required = true (Explicit)
    │          → 중기경쟁 여부 확인 후 해당 시 직생 섹션 표시
    │
    ▼ No
[계약경로 확인] 중기경쟁제품 검증 필수 경로인가?
    ├─ Yes ──→ item_eligibility_required = true (Explicit)
    │          → 중기경쟁 검증 섹션 전면 표시
    │
    ▼ No
[Alias 해소] item_alias_map 결과 중기경쟁 후보가 있는가?
    ├─ Yes ──→ item_eligibility_required = true (Silent)
    │          → 내부 후보 분류만 수행
    │          → 답변에는 보조 문구 1줄만 허용
    │          → 후보표에 직생 열 비표시
    │
    ▼ No
    item_eligibility_required = false
    → Item Eligibility 레이어 완전 스킵
    → ❶~❼ 레이어만으로 답변 조립

─────────────────────────────────────
[업체 후보 조회 완료 후]  ← 별도 타이밍
    │
    ▼
[Enrichment] 후보 업체에 직생 데이터가 존재하는가?
    ├─ Yes ──→ company_candidate_enrichment 실행
    │          → 후보표에 직생 상태를 optional column으로 추가
    │          → 계약 판단에는 영향 없음
    │
    ▼ No
    → 후보표에 직생 열 미표시
```

## 5. 트리거 키워드 목록 (Explicit T1 전용)

```json
{
  "trigger_keywords": [
    "직생",
    "직접생산",
    "직접생산확인",
    "중소기업자간 경쟁제품",
    "중기경쟁",
    "중기경쟁제품",
    "경쟁제품 직접생산",
    "직접생산 확인증"
  ]
}
```

## 6. 등급별 Answer Builder 동작

| 등급 | item_eligibility_required | 답변 본문 | 후보표 직생 열 |
|:----:|:-------------------------:|-----------|:--------------:|
| Explicit | `true` | 별도 섹션으로 직생/중기경쟁 검토 결과 표시 | 전면 표시 |
| Silent | `true` | 보조 문구 1줄만: "해당 품목이 중소기업자간 경쟁제품으로 특정되면 직접생산확인 검토가 필요할 수 있습니다" | **비표시** |
| Enrichment | 해당 없음 (별도 단계) | 언급 안 함 | optional column |
| 미발동 | `false` | 직생/중기경쟁 언급 안 함 | 비표시 |

## 7. 비트리거 사례

| 질문 | 트리거 판정 | 이유 |
|------|:-----------:|------|
| "8천만원 물품 수의계약 가능한가?" | `false` | 키워드 없음, 세부품명 미제공 |
| "부산업체 쓸 수 있는 방법 알려줘" | `false` | 품목 특정 없음, 키워드 없음 |
| "3억 공사 지역제한 가능?" | `false` | 공사, 물품 중기경쟁 무관 |
| "사회적기업 수의계약 한도?" | `false` | 정책기업 특례, 품목 무관 |

## 8. 트리거 사례

| 질문 | 등급 | 해당 조건 |
|------|:----:|-----------|
| "CCTV 직생도 봐줘" | Explicit | T1 (키워드 "직생") |
| "세부품명번호 4617162201" | Explicit | T2 (세부품명 명시) |
| "컴퓨터 구매 방법 알려줘" | Silent | T3 (alias 해소 시 중기경쟁 후보 감지) |
| "CCTV 업체 추천" | Silent | T3 (alias 해소 시 중기경쟁 후보 감지) |
| 업체 후보표 조회 후 직생 데이터 발견 | Enrichment | T4 (업체 인증 데이터) |

## 9. 문서 대체 관계

| 문서 | 상태 |
|------|:----:|
| `item_eligibility_trigger_policy_v0_1_3.md` | **superseded** — 본 문서로 대체 |
| `item_eligibility_rule_integration_plan.md` | superseded |
| `item_eligibility_rule_integration_plan_v0_1_2.md` | superseded |
