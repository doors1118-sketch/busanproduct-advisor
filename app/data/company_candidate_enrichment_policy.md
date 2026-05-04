# Company Candidate Enrichment Policy

본 문서는 T4 트리거(후보 업체에 직접생산확인 데이터 존재)를 **초기 라우팅 트리거가 아닌 업체 후보 조회 후 enrichment 단계**로 분리하는 정책을 정의합니다.

## 1. 문제 정의

v0.1.3에서 T4는 초기 라우팅 단계의 트리거로 배치되어, 후보 업체에 직생 데이터가 있으면 Item Eligibility를 즉시 호출했습니다.
이 설계의 문제점:

1. **타이밍 부적합**: 직생 데이터 존재 여부는 업체 후보가 조회된 이후에야 확인 가능. 초기 라우팅 시점에서는 아직 후보 업체가 특정되지 않음.
2. **판단 오염**: 직생 데이터 존재만으로 계약 판단이 변경될 수 있음.
3. **과도한 노출**: 직생 데이터가 있다는 이유만으로 직생 관련 정보가 답변 전면에 노출.

## 2. Enrichment 단계 정의

T4는 **초기 라우팅과 분리**되어, 지역업체 후보 검색(❻ local_preference) 완료 후 **별도 단계**로 실행됩니다.

### 2.1 실행 타이밍

```
❶~❼ 기본 판단 완료
    │
    ▼
❻ local_preference → 지역업체 후보 목록 생성
    │
    ▼
[Enrichment 단계]
    │  후보 업체 각각에 대해:
    │  company_direct_production_cert_mapping 조회
    │  → 데이터 있으면 후보표에 optional column 추가
    │  → 데이터 없으면 열 미표시
    │
    ▼
Answer Builder
    └── 후보표에 enrichment 결과 반영 (계약 판단과 독립)
```

### 2.2 Enrichment와 Item Eligibility의 관계

| 구분 | Item Eligibility (❽) | Enrichment (T4) |
|------|----------------------|-----------------|
| 실행 조건 | Explicit/Silent 트리거 발동 시 | 업체 후보 조회 완료 후 자동 |
| 판단 영향 | eligibility_context 생성 | **없음** — 계약 판단 불변 |
| 답변 영향 | 트리거 등급에 따라 전면/보조 | 후보표 optional column만 |
| 독립성 | item_eligibility_required에 의존 | item_eligibility_required와 **무관** |

## 3. 후보표 Optional Column 규칙

### 3.1 표시 조건

후보표에 직생 상태 열을 optional column으로 추가하는 조건:

1. 후보 업체 중 **1건 이상**에서 `company_direct_production_cert_mapping` 데이터가 존재
2. 사용자 질문이 **업체 후보 검색/추천**을 포함

위 조건을 **모두** 충족하면 후보표에 "직생 참고" 열을 추가합니다.

### 3.2 열 표시 형식

| 업체명 | 소재지 | 업종 | 실적 | 직생 참고 |
|--------|--------|------|------|-----------|
| 업체A | 부산 해운대구 | 보안장비 | 3건/2억 | 유효 (2027-03 만료) |
| 업체B | 부산 사상구 | 영상장비 | 5건/4억 | — |
| 업체C | 부산 북구 | 전자장비 | 1건/0.5억 | 만료 (갱신 확인 필요) |

### 3.3 열 값 규칙

| 직생 데이터 상태 | 표시 값 |
|-----------------|---------|
| 유효 (valid) | `유효 (YYYY-MM 만료)` |
| 만료 (expired) | `만료 (갱신 확인 필요)` |
| 데이터 없음 | `—` (대시, 빈칸 아님) |

### 3.4 비표시 조건

다음 경우 후보표에 직생 열을 표시하지 않습니다:

- 후보 업체 전체에서 직생 데이터가 0건
- 사용자 질문이 업체 추천이 아닌 순수 법적 해석 질문
- Explicit 트리거(T1/T2/T5)가 발동된 경우 → Explicit 트리거의 후보표 정책이 우선 적용 (전면 표시)

## 4. 금지 행위

| # | 금지 행위 |
|:-:|----------|
| E1 | 직생 데이터 존재만으로 계약 가능성 판단 변경 |
| E2 | 직생 데이터 존재만으로 답변 본문에 직생 섹션 생성 |
| E3 | 직생 유효 업체를 "계약 가능 업체"로 단정 |
| E4 | 직생 데이터 미존재 업체를 후보표에서 자동 제외 |
| E5 | T4 enrichment 결과를 초기 라우팅 판단에 역류시킴 |

## 5. Enrichment와 Explicit의 충돌 해소

Explicit 트리거(T1/T2/T5)와 Enrichment(T4)가 동시에 해당되는 경우:

- **Explicit이 우선**합니다.
- 후보표는 Explicit 정책에 따라 직생 상태를 **전면 표시**합니다 (optional column이 아닌 정규 열).
- Enrichment의 optional column 규칙은 적용하지 않습니다.

예시:
```
Q: "CCTV 부산업체 찾아줘. 직생도 봐줘."
→ T1 (Explicit) + T4 (Enrichment) 동시 발동
→ Explicit 우선 → 후보표에 직생 상태 전면 표시
```

## 6. 기존 문서 대체 관계

| 문서 | 상태 | 비고 |
|------|:----:|------|
| `item_eligibility_trigger_policy_v0_1_3.md` | superseded | T4가 초기 라우팅 트리거로 정의 → 본 문서에서 enrichment로 분리 |
| `item_eligibility_trigger_policy_v0_1_4.md` | 현행 | 트리거 3등급 체계 정의 (본 문서와 함께 참조) |
| `item_eligibility_candidate_table_policy.md` | 유지 (보충) | Explicit 트리거 시 후보표 정책은 기존 문서 적용. Enrichment 시 본 문서 적용 |
