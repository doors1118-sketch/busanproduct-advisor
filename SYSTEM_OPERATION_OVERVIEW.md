# 부산 지역상품 구매지원 지능형 업무 매뉴얼 — 시스템 운영 개요

**작성일**: 2026-05-05  
**버전**: v1.0  
**대상 독자**: 시스템 운영자, 신규 개발자, 관리자

---

## 1. 프로젝트 목적과 배경

### 1.1 해결하려는 문제

| 문제 | 현황 |
|------|------|
| 법적 불안감 | 지역업체 계약 시 감사·위법성 우려로 담당자 망설임 |
| 정보 분산 | 지방계약법·시행령·행안부 예규·조달청 고시·부산시 조례 등에 근거 법령 산재 |
| 검색 시간 | 법령 검색·해석에 건당 약 30분 소요 |
| 낮은 수주율 | 국가공공기관의 부산 지역업체 수주율 31.6% (본청 70.6% 대비) |

### 1.2 시스템이 제공하는 가치

> 계약 담당자가 지역업체와 계약할 때 느끼는 심리적 장벽을 제거하고, 법적 근거를 즉시 제시하여 지역 조달 수주율을 제고한다.

### 1.3 3대 핵심 기능

```
사용자 질문
    ↓
❶ 지역업체 활용 계약절차 안내 (절차)
❷ 지역업체 보호제도 법적 해석 (법령)
❸ 지역업체 추천 (업체 검색)
```

### 1.4 대상 사용자

| 대상 | 시나리오 |
|------|----------|
| 부산시·구군 계약 담당 공무원 | 지역제한 입찰 가능 여부, 수의계약 한도 확인 |
| 출자·출연기관 담당자 | 기관 내규 + 상위법 교차 확인 |
| 관내 국가기관 계약 담당자 | 지역업체 정보 조회, 계약가능성 사전 검토 |

---

## 2. 시스템 아키텍처

### 2.1 기술 스택

| 구성요소 | 기술 |
|----------|------|
| AI 엔진 | Google Gemini API (Flash 기본, Pro fallback) |
| 법령 검색 | Korean Law MCP (법제처 Open API) |
| 내규 검색 | ChromaDB 기반 자체 RAG |
| 업체 DB | PostgreSQL (자체 모니터링 시스템, 20,000+ 부산 업체) |
| 백엔드 | FastAPI (Python) |
| 프론트엔드 | Streamlit (Web UI) |
| 인프라 | NCP (Naver Cloud Platform) |

### 2.2 7-Stage 런타임 파이프라인

```
사용자 질문: "부산항만공사가 8천만원 LED조명을 구매하려면?"
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Chatbot Runtime Orchestrator                        │
│                                                     │
│  Stage 1: Intent Router (Gemini + Deterministic)    │
│  Stage 2: Gateway (Legal DB Resolver)               │
│  Stage 3: Rule Engine (Decision Context)            │
│  Stage 4: Company API Adapter (mock/live)           │
│  Stage 5: Evidence Context Loader                   │
│  Stage 6: Answer Type Router + Builder              │
│  Stage 7: Forbidden Phrase Re-scan                  │
│                                                     │
│  → ChatbotRuntimeResponse                           │
└─────────────────────────────────────────────────────┘
```

### 2.3 Gemini 역할 정의

> **핵심 설계 원칙**: Gemini는 "판단 계층"이 아닌 **"구조화 전용 해석 계층"**으로 격리된다. 최종 판단은 결정론적 Slot Repair 및 내부 API 어댑터를 통해 수행한다.

```
Gemini의 역할:
  ✅ 사용자 질문 → 구조화된 JSON (intent, slots) 추출
  ✅ 비정형 한국어 → 영문 Canonical Value 변환
  ❌ 법적 결론 판단 (금지)
  ❌ 수치 기준 산출 (금지)
  ❌ 계약 가능/불가 판정 (금지)
```

### 2.4 Gemini 장애 대응 흐름

```
Flash 호출
    │
    ├─ 성공 → JSON 파싱 → 정규화 → Slot Repair → 답변 생성
    │
    ├─ JSON 파싱 실패 → Raw Text에서 슬롯 구출(salvage)
    │   └─ Slot Repair로 정상 Flow 승격 → 성공 시 Retry/Pro 생략
    │
    ├─ api_key_invalid → Retry/Pro 즉시 차단 → Slot Repair만 적용
    │
    ├─ 기타 실패 → Flash 1회 재시도
    │
    └─ 최종 실패 → Pro Fallback (결과에 이유 기록)
```

---

## 3. 핵심 모듈 설명

### 3.1 Intent Router (`app/router/`)

사용자의 자연어 질문을 **8종 Intent**와 **구조화된 Slots**로 변환한다.

**지원 Intent (8종)**:

| Intent | 설명 | 예시 |
|--------|------|------|
| `legal_explanation` | 법령·제도 설명 | "수의계약이 뭐야?" |
| `contract_review` | 구체적 계약 검토 | "LED조명 1억원 구매 방법" |
| `local_purchase_support` | 지역업체 구매지원 | "부산업체 우선 구매 제도" |
| `candidate_search` | 후보업체 조회 | "CCTV 부산 업체 추천해줘" |
| `item_eligibility` | 품목 자격 검토 | "직접생산확인 대상인가요?" |
| `procurement_route_review` | 조달경로 검토 | "MAS와 제3자단가 차이" |
| `mixed` | 복합 의도 | 위 의도가 2개 이상 혼합 |
| `out_of_scope` | 범위 밖 | "오늘 날씨 어때?" |

**RouterSlots 주요 필드**:

| 필드 | 타입 | 설명 | 예시 |
|------|------|------|------|
| `amount` | int | 추정가격 | 100000000 |
| `item_name` | str | 품목명 | LED조명 |
| `contract_object` | str | 계약목적물 | goods/service/construction |
| `company_type` | str | 업체유형 | women/disabled/general |
| `quote_type` | str | 견적유형 | 1_quote/2_quote |
| `contract_method` | str | 계약방식 | direct_contract/competitive_bid |
| `candidate_lookup_requested` | bool | 업체 조회 요청 여부 | true/false |

### 3.2 Answer Builder (`app/answer_builder/`)

RouterResult의 `routing_decision`에 따라 적절한 답변 빌더를 선택한다.

| routing_decision | 빌더 함수 | 출력 섹션 |
|------------------|-----------|----------|
| `contract_review_flow` | `build_contract_review` | 계약 요약(금액·품목·업체유형·견적유형) + 구매지원 + 품목 자격 |
| `mixed_flow` | `build_mixed_flow` | 계약 검토 요약 + 조달경로 + 지역업체 + 후보조회 + 품목자격 |
| `legal_explanation_flow` | `build_legal_explanation` | 법령 설명 + 참고 안내 |
| `candidate_search_flow` | `build_candidate_search` | 조회 조건 + 조회 결과 |
| `clarification_required` | `build_clarification` | 추가 정보 요청 |
| `out_of_scope` | `build_out_of_scope` | 범위 밖 안내 |

### 3.3 Evidence-Based Answer Builder

법령 근거의 검증 수준(display_level)에 따라 답변 내 표시 수준을 차등 적용한다.

| display_level | 의미 | 답변 내 표시 |
|---------------|------|-------------|
| `source_verified` | 검증된 source 확인 | 조문 발췌 표시 가능 |
| `source_candidate` | 후보 있으나 검토 필요 | "검토 상태 확인 필요" |
| `partial_evidence` | 일부 근거만 존재 | "미매핑 항목 확인 필요" |
| `source_missing` | 직접 근거 미확인 | "원문 확인 필요" |
| `company_api_only` | 업체 API 연동 대상 | API 조회 결과 표시 |

**수치 출력 정책**:
- `resolved_value`가 없으면 수치 출력 금지
- 사용자 입력 금액(예: "추정가격: 100,000,000원")은 항상 보존
- 금액 미입력 질의에는 기준금액 NOTE 박스 미노출

### 3.4 Company API Adapter

| 항목 | 수치 |
|------|------|
| 부산 소재 업체 수 | 20,000+ |
| 면허 업종 수 | 18,678 |
| 인증제품 데이터 | 112,803건 |

**안전 정책**:
- HMAC-SHA256 기반 비식별 company_id (사업자등록번호 비노출)
- 대표자명, 이메일, 사업자등록번호 PII 미노출
- 후보업체 "상태: 검토 후보" 라벨링 (적격 확정 표현 금지)

---

## 4. 안전 정책 (Fail-Closed Safety)

### 4.1 금지 표현

| 금지 표현 | 이유 |
|----------|------|
| "계약 가능합니다" | 법적 결론 단정 금지 |
| "구매 가능합니다" | 법적 결론 단정 금지 |
| "수의계약 가능합니다" | 법적 결론 단정 금지 |
| "지역제한 가능합니다" | 법적 결론 단정 금지 |
| "낙찰 가능합니다" | 법적 결론 단정 금지 |

### 4.2 금지 표현 감지 시 동작

1. `forbidden_phrase_scan_passed = False`
2. `runtime_status = "degraded"`
3. 전체 `rendered_markdown`을 안전 fallback 문구로 교체
4. 모든 구조화 섹션 (`candidate_table`, `local_purchase_support` 등) `None`으로 제거

### 4.3 API 오류 보안

- Gemini API 오류 시 상세 에러 전문(Traceback, PII) 비노출
- 메타데이터에 `api_key_invalid` 또는 `api_call_failed` 요약 코드만 기록
- `api_key_invalid` 발생 시 Retry/Pro Fallback 즉시 차단 (비용 낭비 방지)

---

## 5. 법령 DB 체계

### 5.1 법령 소스 계층

```
L1 법률    ── 지방계약법, 국가계약법, 조달사업법
L2 시행령  ── 각 법률의 시행령
L3 시행규칙 ── 각 법률의 시행규칙
L4 행정규칙 ── 행안부 예규, 조달청 훈령/고시, 부산시 조례
L5 조달문서 ── MAS 특수조건, 제3자단가 특수조건
```

### 5.2 수집 현황

| 그룹 | 대상 | 수량 |
|------|------|------|
| A | 국가계약법 계열 | 6건 |
| B | 지방계약법 계열 | 6건 |
| C | 행안부 예규 | 6건 |
| D | 조달청 훈령/고시 | 10건 |
| E | 지방공기업법 계열 | 3건 |
| F | 부산시 조례, 중기부 고시 | 6건 |
| **합계** | | **37건** |

### 5.3 Rule Catalog & Source Map

- **Rule Catalog**: 37개 규칙 (61KB)
- **Source Map**: 37개 규칙별 법령 매핑 (179KB)
- **Source Chain Status**: `partial_mapped` 27건, `mapped_verified` 2건, `mapped_candidate` 2건, `pending_resolution` 2건, `company_api_mapping_required` 4건

---

## 6. 테스트 체계

### 6.1 단위/회귀 테스트

| 테스트 파일 | 검증 대상 |
|-------------|----------|
| `test_evidence_policy.py` | display_level 분류, numeric display 판정 |
| `test_evidence_context_loader.py` | rule 추론, contract_object 분기 |
| `test_evidence_answer_builder.py` | evidence section 삽입, 금지표현 차단 |
| `test_chatbot_runtime_orchestrator.py` | orchestrator 전체 흐름 |
| `test_gemini_intent_router.py` | JSON 파싱, confidence fallback |
| `test_api_error_fallback.py` | API 에러 시 안전 fallback |
| 기타 10개 파일 | 각 모듈별 검증 |

### 6.2 Live E2E 테스트

`scratch/run_live_e2e_with_gemini.py`로 실제 Gemini API를 태운 6개 시나리오 검증.

| Scenario | 질의 | 검증 포인트 |
|----------|------|-------------|
| 1 | CCTV 부산 업체 | 품목 적격성 + Company API 동시 |
| 2 | LED조명 1억원 구매 | 금액 표시, 품목 적격성, 단정 금지 |
| 3 | 여성기업 4천만원 1인 견적 | 정책기업 기준 표시 |
| 4 | 일반기업 3천만원 2인 견적 | 소액수의 우선 경로 배제 |
| 5 | 컴퓨터 부산 업체 추천 | 후보업체 표, '검토 후보' 표시 |
| 6 | 수의계약 가능합니다 업체 찾아줘 | 금지 표현 차단, 조건별 안내형 Evidence |

### 6.3 리포트 판정 구조

```
- Gemini API Status: OK / FAILED_API_KEY_INVALID
- Slot Repair Used: YES / NO
- Slot Repair Needed: YES / NO
- Slot Repair Recovery: NOT_NEEDED / PASS / FAIL
- Scenario Functional Status: PASS / FAIL
```

---

## 7. 운영 환경

### 7.1 서버 구성

| 항목 | 값 |
|------|------|
| 호스팅 | NCP (Naver Cloud Platform) |
| OS | Ubuntu |
| 서비스 | law-chatbot.service (포트 8502) |
| MCP 서비스 | korean-law-mcp.service |
| 배포 스크립트 | deploy_chatbot.sh |

### 7.2 환경 변수

```
GEMINI_API_KEY                    # Google Gemini API 키
MONITORING_COMPANY_API_BASE_URL   # 모니터링 시스템 API 주소
PILOT_PASSWORD                    # 파일럿 접근 비밀번호
```

### 7.3 현재 배포 상태

```
production_deployment = HOLD
내부 파일럿 테스트 진행 중
```

---

## 8. 향후 운영 방향

### 8.1 단기 (1~2주)

| 우선순위 | 작업 | 설명 |
|----------|------|------|
| **P0** | 핵심 규칙 수동 매핑 | partial_mapped 27건 중 핵심 5~8개 규칙 우선 정밀 매핑 |
| **P0** | 수치 파라미터 확정 | 수의계약 기준금액 등 resolved_value 채움 |
| **P1** | /chat API endpoint | Orchestrator → Web UI / API endpoint 연결 |
| **P1** | Gateway/Rule Engine stub 해제 | 실제 Legal DB + Rule Engine 연동 |

### 8.2 중기 (3~4주)

| 작업 | 설명 |
|------|------|
| 조문 단위 색인 | 별표/본문 추출, 조문별 벡터 임베딩 |
| 법령 업데이트 자동화 | Diff Engine으로 개정 사항 자동 반영 |
| Live Company API 전환 | staging 환경에서 실 업체 DB 연동 |
| 기관유형별 법체계 분기 | 지방자치단체/공기업/국가기관별 적용법 분기 |

### 8.3 장기 (1~2개월)

| 작업 | 설명 |
|------|------|
| 카카오톡 / 텔레그램 챗봇 연동 | 메신저 채널 확장 |
| 운영 모니터링 대시보드 | 질의 로그, 응답 품질, 금지 표현 발생 추적 |
| 사용자 피드백 수집 | 답변 만족도, 오답 신고 |
| 내부 파일럿 → 정식 운영 | 보안 감사, 접근 통제, SLA 정의 |
| `google.genai` 마이그레이션 | 현재 `google.generativeai` 패키지 지원 종료 대비 |

### 8.4 Source Gap 해소 전략 (ChatGPT 평가서 반영)

현재 Source Map의 27개 `partial_mapped` 규칙 중 대부분이 **키워드 유사도 기반의 오매핑** 상태이다. 전체를 일괄 수정하기보다 아래 순서로 점진적 해소가 권장된다:

| 순서 | 전략 | 설명 |
|------|------|------|
| 1단계 | 핵심 규칙 수동 매핑 | 소액수의(R_DIRECT), 지역제한(R_REGIONAL), MAS 2단계 등 5~8개 우선 |
| 2단계 | /chat API 먼저 연결 | 최소 서비스 → 실사용자 피드백 → 필요한 규칙부터 보강 |
| 3단계 | 조문 단위 색인 구축 | 시행령 텍스트에서 조문 번호 파싱 → 정밀 자동 매핑 |

> 설계 원칙(안전성·투명성·역할 분리)은 전적으로 타당하다. 다만 데이터 완성을 코드 통합보다 먼저 강제하는 것은 병목이 될 수 있으므로, "최소 서비스 → 점진 보강" 전략이 현실적이다.

---

## 9. 핵심 설계 원칙 요약

| 원칙 | 설명 |
|------|------|
| **법적 결론 단정 금지** | "가능합니다" 대신 "검토 기준", "확인 필요"로 표현 |
| **수치 하드코딩 금지** | 법령 개정 시 자동 오답 방지 |
| **사용자 금액 보존** | 입력값과 법령기준값을 명확히 구분 |
| **Evidence-Based 투명성** | "무엇을 확인해야 하는지" 먼저 보여주는 접근 |
| **Fail-Closed 안전성** | 금지 표현 감지 시 전체 답변 교체 |
| **Gemini 해석 전용** | LLM은 구조화만, 판단은 결정론적 계층에서 수행 |
| **Gateway read-only** | 판단/write/LLM 분리 |
| **PII 비노출** | API 오류 트레이스, 사업자등록번호, 대표자명 등 미노출 |

---

*본 문서는 프로젝트 현황 보고서(PART1, PART2) 및 개발방향 적합성 평가(chatgpt_direction_evaluation.md)를 기반으로 종합 작성되었습니다.*
