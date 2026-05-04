# 부산 지역상품 구매지원 지능형 업무 매뉴얼 — 코드 상세 및 향후 계획

**작성일**: 2026-05-05  
**Part 2/2** — Part 1 (PROJECT_OVERVIEW_PART1.md)에서 이어짐

---

## 7. 코드 구조 상세

### 7.1 디렉토리 구조

```
메뉴얼 제작/
├── app/                              # 핵심 애플리케이션
│   ├── 🏠_홈.py                      # Streamlit 메인 페이지
│   ├── api_server.py                 # FastAPI 백엔드 (포트 8502)
│   ├── gemini_engine.py              # Gemini 통합 엔진 (186KB, 핵심)
│   ├── system_prompt.py              # 시스템 프롬프트 (57KB)
│   ├── company_api.py                # 모니터링 시스템 API 클라이언트
│   ├── law_api_client.py             # 법제처 API 클라이언트
│   ├── mcp_client.py                 # Korean Law MCP 클라이언트
│   ├── embedding.py                  # ChromaDB 임베딩
│   ├── warmup.py                     # 캐시 워밍업
│   │
│   ├── router/                       # Intent Router 계층
│   │   ├── intent_schema.py          # RouterResult, RouterSlots 스키마
│   │   ├── gemini_intent_router.py   # Gemini JSON 응답 파싱
│   │   ├── deterministic_intent_validator.py  # 결정론적 보정
│   │   └── router_prompt.py          # Router 전용 프롬프트
│   │
│   ├── answer_builder/               # 답변 생성 계층
│   │   ├── schema.py                 # AnswerBuilderOutput 스키마
│   │   ├── answer_type_router.py     # 5개 flow 라우팅
│   │   ├── builder.py                # 기존 빌더 (v0.1)
│   │   ├── evidence_schema.py        # Evidence 모델 정의
│   │   ├── evidence_policy.py        # display_level 분류, numeric gating
│   │   ├── evidence_context_loader.py # Source Map → EvidenceContext
│   │   └── evidence_answer_builder.py # Evidence section 생성
│   │
│   ├── gateway/                      # Legal MCP Gateway 계층
│   │   ├── gateway.py                # 통합 게이트웨이
│   │   ├── models/                   # 요청/응답 모델
│   │   ├── resolvers/                # Source/Item/Route/Procedure/Company
│   │   └── db/                       # Legal DB 접근
│   │
│   ├── rule_engine/                  # 법적 규칙 엔진
│   │   ├── engine.py                 # 8단계 우선순위 엔진
│   │   └── decision_context.py       # DecisionContext 구조
│   │
│   ├── runtime/                      # 런타임 오케스트레이터
│   │   ├── chatbot_orchestrator.py   # 7-stage 파이프라인
│   │   ├── company_api_adapter.py    # Company API mock/live 어댑터
│   │   └── runtime_schema.py         # 런타임 스키마
│   │
│   ├── policies/                     # 정책 문서
│   ├── data/                         # 법령 DB + 정책 데이터 (148 파일)
│   ├── pages/                        # Streamlit 추가 페이지
│   └── prompting/                    # 프롬프트 관련
│
├── tests/                            # 테스트 (16개 파일, 181건)
├── docs/                             # 문서
├── frontend/                         # 프론트엔드 정적 파일
├── config/                           # 설정
├── scripts/                          # 유틸리티 스크립트
├── prompts/                          # 프롬프트 템플릿
│
├── legal_db_v0_1_3.sqlite           # 법령 DB (397KB)
├── purchase_support_rule_source_map.json  # 37 규칙별 source 매핑 (179KB)
├── local_purchase_support_rule_catalog.json  # 37 규칙 카탈로그 (61KB)
├── 사용목적_개발방향.md              # 프로젝트 방향 문서
└── 공공계약_법령챗봇_개발계획서.md    # 개발 계획서
```

### 7.2 핵심 모듈별 역할

#### 7.2.1 Intent Router (`app/router/`)

```
사용자 질문 → GeminiIntentRouter.parse_gemini_response(mock/live)
           → DeterministicIntentValidator.validate()
           → RouterResult {
               primary_intent,     # 주 의도 (8종)
               secondary_intents,  # 부가 의도
               slots,              # 구조화 정보 (기관명, 금액, 품목 등)
               routing_decision,   # flow 결정
               clarification_needed  # 추가 필요 정보
             }
```

**지원 Intent (8종)**:
- `legal_explanation` — 법령·제도 설명
- `contract_review` — 구체적 계약 검토
- `local_purchase_support` — 지역업체 구매지원
- `candidate_search` — 후보업체 조회
- `item_eligibility` — 품목 자격 검토
- `procurement_route_review` — 조달경로 검토
- `mixed` — 복합 의도
- `out_of_scope` — 범위 밖

**Deterministic Validator 보정 규칙**:
- 지역업체/부산업체 키워드 → `local_purchase_support` 추가
- MAS/다수공급자계약 키워드 → `procurement_route=mas` slot 보정
- 설명형 동사 (뭐야, 차이가 뭐야) → `is_pure_explanation` 감지
- 실행형 동사 (구매하려고, 어떻게 해야 해) → `contract_review` 추가

#### 7.2.2 Answer Type Router (`app/answer_builder/`)

| routing_decision | 빌더 | 출력 섹션 |
|------------------|-------|----------|
| `legal_explanation_flow` | `build_legal_explanation` | 법령 설명 + 참고 안내 |
| `contract_review_flow` | `build_contract_review` | 계약 요약 + 구매지원 + 조달경로 + 품목 자격 |
| `local_purchase_support_flow` | `build_contract_review` | 동일 (MVP) |
| `candidate_search_flow` | `build_candidate_search` | 조회 조건 + 조회 결과 |
| `mixed_flow` | `build_mixed_flow` | 순서별 섹션화 |
| `out_of_scope` | `build_out_of_scope` | 범위 밖 안내 |
| `clarification_required` | `build_clarification` | 추가 정보 요청 |

#### 7.2.3 Evidence-Based Answer Builder (Phase 10.5)

```
EvidenceContext
  ├── active_rule_ids: [R_DIRECT_GENERAL_SMALL_AMOUNT, R_REGIONAL_RESTRICTION_GOODS, ...]
  ├── rule_statuses:
  │   ├── display_level: source_verified → "검증된 source 후보 확인"
  │   ├── display_level: source_candidate → "검토 상태 확인 필요"
  │   ├── display_level: partial_evidence → "미매핑 항목/수치 확인 필요"
  │   ├── display_level: source_missing → "직접 근거 확인 필요"
  │   └── display_level: company_api_only → "업체 후보 조회 API 대상"
  ├── source_gap_exists: true/false
  └── unresolved_numeric_exists: true/false
```

**수치 출력 정책**:
- `resolved_value`가 없으면 수치 출력 금지
- `expected_value_hint`는 내부 힌트, 사용자 답변에 미노출
- 사용자 입력 금액 (예: "추정가격: 50,000,000원")은 보존

#### 7.2.4 Runtime Orchestrator (`app/runtime/`)

```python
# 7-stage 파이프라인
Stage 1: intent_router       # Gemini + Deterministic Validation
Stage 2: gateway              # Legal DB Resolver (stub)
Stage 3: rule_engine           # Decision Context (stub)
Stage 4: company_candidate_resolver  # Company API (mock/live)
Stage 5: evidence_context      # Evidence Builder (optional)
Stage 6: answer_builder        # Answer Type Router + Builder
Stage 7: forbidden_rescan      # 금지 표현 최종 검사

# runtime_options 예시
{
    "use_mock_company_api": true,    # Company API mock 모드
    "use_evidence_builder": true,     # Evidence Builder 활성화
    "source_map_path": "custom.json"  # 커스텀 source map
}
```

### 7.3 금지 표현 (Fail-Closed Safety)

| 금지 표현 | 이유 |
|----------|------|
| "계약 가능합니다" | 법적 결론 단정 금지 |
| "구매 가능합니다" | 법적 결론 단정 금지 |
| "수의계약 가능합니다" | 법적 결론 단정 금지 |
| "지역제한 가능합니다" | 법적 결론 단정 금지 |
| "낙찰 가능합니다" | 법적 결론 단정 금지 |

**감지 시 동작**:
1. `forbidden_phrase_scan_passed = False`
2. `runtime_status = "degraded"`
3. 전체 `rendered_markdown`을 안전 fallback 문구로 교체
4. 모든 구조화 섹션 (`candidate_table`, `local_purchase_support` 등) `None`으로 제거

---

## 8. 주요 데이터 파일

| 파일 | 크기 | 용도 |
|------|------|------|
| `legal_db_v0_1_3.sqlite` | 397KB | 법령 DB (법률+시행령+예규+고시) |
| `purchase_support_rule_source_map.json` | 179KB | 37 규칙별 법령 source 매핑 |
| `local_purchase_support_rule_catalog.json` | 61KB | 37개 규칙 카탈로그 |
| `legal_source_registry.json` | 109KB | 법령 소스 레지스트리 |
| `legal_update_manifest.json` | 241KB | 법령 업데이트 매니페스트 |
| `app/policy_companies.json` | 1MB | 정책기업 목록 |
| `app/gemini_engine.py` | 186KB | Gemini 통합 엔진 (핵심) |
| `app/system_prompt.py` | 57KB | 시스템 프롬프트 |
| `chroma.zip` | 45MB | ChromaDB RAG 벡터 DB |

---

## 9. 주요 커밋 이력 (시간순)

| 날짜 | 커밋 | 내용 |
|------|------|------|
| 04/21 | `793d8ca` | 초기 코드 — Korean Law MCP + Gemini FC + NCP 배포 |
| 04/22 | `6ec40eb` | MCP-RAG 우선순위, 행정규칙 검색, 매뉴얼 RAG 적재 |
| 04/25 | `3ff82d9` | 시스템 프롬프트 MCP 위임 리팩토링 |
| 04/26 | `d82ba0f` | risk-based model routing + TC8 static validation |
| 04/27 | `54ee940` | staging 검증 PASS, TC7 latency 최적화 |
| 04/28 | `a60fc06` | 금액 기반 수의계약 경로 안내 기능 |
| 04/30 | `bfc1bef` | Phase 5 답변속도 회귀 방지 |
| 05/01 | `08c0ec4` | CacheBuilder MVP, HMAC 정규화, live API |
| 05/02 | `c2f55d4` | Legal DB SQLite 커밋 |
| 05/02 | `86c0ce6` | Phase 7 Final Baseline 동결 |
| 05/03 | `385cd04` | Phase 8 Gateway Skeleton |
| 05/03 | `641ae4e` | Real DB Resolver 연동 |
| 05/03 | `99a0a8c` | Phase 9.3 Gemini Intent Router |
| 05/04 | `8c5fa14` | Phase 9.2 Rule Catalog + Source Chain |
| 05/04 | `bfcb416` | Phase 10.2 Answer Type Router v0.2 |
| 05/04 | `6acf238` | Phase 10.4 Runtime Orchestrator |
| 05/04 | `6352cb6` | Phase 8.3 Company API Adapter 연동 |
| 05/04 | `af35136` | Phase 10.5 Evidence-Based Answer Builder |
| 05/05 | `c776130` | Evidence scan metadata 보완 (현재) |

---

## 10. 향후 진행 계획

### 10.1 단기 (1~2주)

| 우선순위 | Phase | 작업 | 설명 |
|----------|-------|------|------|
| **P0** | 9.2-D | Source Chain Completion | partial_mapped 27건 → mapped_verified 승격 |
| **P0** | - | 수치 파라미터 확정 | 수의계약 기준금액, MAS 2단계 기준 등 resolved_value 채움 |
| **P1** | 10.6 | Evidence-Based Builder 고도화 | source chain 완료 후 확정 근거 답변 생성 |
| **P1** | - | Gateway/Rule Engine stub 해제 | 실제 Legal DB + Rule Engine 연동 |
| **P2** | 11 | 프론트엔드 통합 | Orchestrator → Web UI / API endpoint 연결 |

### 10.2 중기 (3~4주)

| Phase | 작업 | 설명 |
|-------|------|------|
| 12 | 조문 단위 색인 | 별표/본문 추출, 조문별 벡터 임베딩 |
| 13 | 법령 업데이트 자동화 | Diff Engine으로 개정 사항 자동 반영 |
| 14 | Live Company API 전환 | staging 환경에서 실 업체 DB 연동 테스트 |
| 15 | 기관유형별 법체계 분기 | 지방자치단체/공기업/국가기관별 적용법 분기 |

### 10.3 장기 (1~2개월)

| Phase | 작업 | 설명 |
|-------|------|------|
| 16 | 카카오톡 챗봇 연동 | 메신저 채널 확장 |
| 17 | 텔레그램 챗봇 연동 | 메신저 채널 확장 |
| 18 | 운영 모니터링 대시보드 | 질의 로그, 응답 품질, 금지 표현 발생 추적 |
| 19 | 사용자 피드백 수집 | 답변 만족도, 오답 신고 |
| 20 | 내부 파일럿 → 정식 운영 | 보안 감사, 접근 통제, SLA 정의 |

### 10.4 Source Gap Backlog (미완)

아래 항목은 Source Chain Completion에서 해결해야 한다:

| # | 항목 | 현재 상태 |
|---|------|----------|
| 1 | 지역제한 / 제한경쟁 기준금액 | partial_mapped |
| 2 | 수의계약 1인·2인 견적 및 금액 기준 | partial_mapped |
| 3 | 제3자단가계약 / 납품요구 | partial_mapped |
| 4 | 지역업체 평가항목 / 배점 (7.5점, 40%, 49%) | partial_mapped |
| 5 | 사회적가치 / 중증장애인생산품 | partial_mapped |
| 6 | MAS 2단계경쟁 기준금액 (5천만원, 1억원) | partial_mapped |

---

## 11. 운영 정보

### 11.1 서버 구성

| 항목 | 값 |
|------|------|
| 호스팅 | NCP (Naver Cloud Platform) |
| OS | Ubuntu |
| 서비스 | law-chatbot.service (포트 8502) |
| MCP 서비스 | korean-law-mcp.service |
| 배포 스크립트 | deploy_chatbot.sh |

### 11.2 환경 변수

```
GEMINI_API_KEY                    # Google Gemini API 키
MONITORING_COMPANY_API_BASE_URL   # 모니터링 시스템 API 주소
PILOT_PASSWORD                    # 파일럿 접근 비밀번호
```

### 11.3 배포 상태

```
production_deployment = HOLD
내부 파일럿 테스트 진행 중
```

---

## 12. 참고 문서

| 문서 | 위치 |
|------|------|
| 사용목적 및 개발방향 | `사용목적_개발방향.md` |
| 개발계획서 | `공공계약_법령챗봇_개발계획서.md` |
| API 문서 | `API.md` |
| 아키텍처 문서 | `ARCHITECTURE.md` |
| 개발 가이드 | `DEVELOPMENT.md` |
| Phase 7 Handoff | `app/data/phase7_final_handoff_report.md` |
| Phase 8 Gateway 설계 | `app/data/phase8_gateway_design.md` |
| Phase 8 API Spec | `app/data/phase8_gateway_api_spec.md` |
| Rule Engine 설계 | `phase9_rule_engine_v0_1_design.md` |
| Source Chain Report | `purchase_support_source_chain_discovery_report.md` |
| 작업 지침 | `WORK_GUIDELINE.md` |
