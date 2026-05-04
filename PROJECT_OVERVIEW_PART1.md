# 부산 지역상품 구매지원 지능형 업무 매뉴얼 — 프로젝트 현황 보고서

**작성일**: 2026-05-05  
**Repository**: [busanproduct-advisor](https://github.com/doors1118-sketch/busanproduct-advisor)  
**총 커밋 수**: 162건  
**개발 기간**: 2026-04-21 ~ 현재 (약 2주)

---

## 1. 프로젝트 개요

### 1.1 목적

> 계약 담당자가 지역업체와 계약할 때 느끼는 심리적 장벽을 제거하고, 법적 근거를 즉시 제시하여 지역 조달 수주율을 제고한다.

| 문제 | 현황 |
|------|------|
| 법적 불안감 | 지역업체 계약 시 감사·위법성 우려로 담당자 망설임 |
| 정보 분산 | 지방계약법·시행령·행안부 예규·조달청 고시·부산시 조례 등에 근거 법령 산재 |
| 검색 시간 | 법령 검색·해석에 건당 약 30분 소요 |
| 낮은 수주율 | 국가공공기관의 부산 지역업체 수주율 31.6% (본청 70.6% 대비) |

### 1.2 대상 사용자

| 대상 | 시나리오 |
|------|----------|
| 부산시·구군 계약 담당 공무원 | 지역제한 입찰 가능 여부, 수의계약 한도 확인 |
| 출자·출연기관 담당자 | 기관 내규 + 상위법 교차 확인 |
| 관내 국가기관 계약 담당자 | 지역업체 정보 조회, 계약가능성 사전 검토 |

### 1.3 3대 핵심 기능

```
사용자 질문
    ↓
❶ 지역업체 활용 계약절차 안내 (절차)
❷ 지역업체 보호제도 법적 해석 (법령)
❸ 지역업체 추천 (업체 검색)
```

### 1.4 기술 스택

| 구성요소 | 기술 |
|----------|------|
| AI 엔진 | Google Gemini API (function calling) |
| 법령 검색 | Korean Law MCP (법제처 Open API) |
| 내규 검색 | ChromaDB 기반 자체 RAG |
| 업체 DB | PostgreSQL (자체 모니터링 시스템, 20,000+ 부산 업체) |
| 백엔드 | FastAPI (Python) |
| 프론트엔드 | Streamlit (Web UI) |
| 인프라 | NCP (Naver Cloud Platform) |
| 메신저 | 카카오톡 / 텔레그램 (예정) |

---

## 2. 시스템 아키텍처

```
사용자 질문: "부산항만공사가 8천만원 LED조명을 구매하려면?"
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Chatbot Runtime Orchestrator                        │
│                                                     │
│  Stage 1: Intent Router (Gemini + Deterministic)    │
│  Stage 2: Gateway (Legal DB Resolver) ──── stub     │
│  Stage 3: Rule Engine (Decision Context) ── stub    │
│  Stage 4: Company API Adapter (mock/live)           │
│  Stage 5: Evidence Context Loader (optional)        │
│  Stage 6: Answer Type Router + Builder              │
│  Stage 7: Forbidden Phrase Re-scan                  │
│                                                     │
│  → ChatbotRuntimeResponse                           │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  Data Layer                                          │
│                                                     │
│  ┌──────────────┐ ┌────────────────────┐            │
│  │ Legal DB      │ │ Company API        │            │
│  │ (SQLite)      │ │ (Internal REST)    │            │
│  │ 37 법령 source │ │ 20,000+ 부산업체   │            │
│  └──────────────┘ └────────────────────┘            │
│                                                     │
│  ┌──────────────┐ ┌────────────────────┐            │
│  │ ChromaDB RAG │ │ Rule Catalog       │            │
│  │ 법령+매뉴얼   │ │ 37 규칙, Source Map │            │
│  └──────────────┘ └────────────────────┘            │
└─────────────────────────────────────────────────────┘
```

---

## 3. 개발 Phase별 진행 내역

### Phase 1–3: 기초 인프라 구축 (04/21 ~ 04/24)

| 항목 | 내용 | 상태 |
|------|------|------|
| Korean Law MCP 연동 | 법제처 Open API 기반 법령·판례 실시간 검색 | ✅ 완료 |
| Gemini Function Calling | 8개 도구 통합 (법령검색, 판례검색, 조문조회 등) | ✅ 완료 |
| ChromaDB RAG 구축 | 법령·매뉴얼·조달청 QA 867건 벡터 적재 | ✅ 완료 |
| 시스템 프롬프트 설계 | 법령 근거 기반 답변, 금지 표현 정의 | ✅ 완료 |
| NCP 서버 배포 | law-chatbot.service + korean-law-mcp.service | ✅ 완료 |
| Streamlit 웹 UI | 챗봇 + 업체검색 + 예시질문 + 다운로드 기능 | ✅ 완료 |

### Phase 4: 파일럿 테스트 준비 (04/25 ~ 04/27)

| 항목 | 내용 | 상태 |
|------|------|------|
| Basic Auth 인증 | 파일럿 접근 제한 | ✅ 완료 |
| CSV Injection Guard | 후보 테이블 다운로드 보안 | ✅ 완료 |
| TC7 시나리오 검증 | 7개 라우팅 시나리오 × 확장 변형 | ✅ 완료 |
| TC8 결정론적 라우팅 | 8개 정적 검증 시나리오 | ✅ 완료 |
| 스트레스 테스트 | 동시 10건 부하 테스트 | ✅ 완료 |

### Phase 5: 답변 오케스트레이션 고도화 (04/28 ~ 05/01)

| 항목 | 내용 | 상태 |
|------|------|------|
| 금액 기반 계약경로 안내 | 추정가격 파싱 → 수의계약/경쟁입찰 분기 | ✅ 완료 |
| 지역업체 우선 경로 안내 | 지역제한·지역가점·지역의무공동도급 안내 | ✅ 완료 |
| 캐시 상태 표시 | per-row cache_hit, source_status | ✅ 완료 |
| MAS phantom row 제거 | 잘못된 MAS 행 제거 | ✅ 완료 |
| 응답속도 최적화 | Tier 0 latency 측정, 15초 이내 목표 | ✅ 완료 |

### Phase 6: 모니터링 시스템 연동 (05/01 ~ 05/02)

| 항목 | 내용 | 상태 |
|------|------|------|
| company_api.py 재작성 | 레거시 제거, 내부 API 전환 | ✅ 완료 |
| HMAC-SHA256 업체 ID | 사업자등록번호 비식별화 (Hash-Only) | ✅ 완료 |
| /api/chatbot/ 전용 라우터 | 대시보드 트래픽과 분리 | ✅ 완료 |
| List / Detail 분리 | PII 노출 최소화, LLM 토큰 절약 | ✅ 완료 |
| NTS 사업자 조회 | 휴·폐업 자동 필터링 | ✅ 완료 |
| alert_check.py | ETL 실패 시 SMS/Email 알림 | ✅ 완료 |
| chatbot_company_candidate_view | 구조화된 메타데이터 API | ✅ 완료 |

### Phase 7: 법령 DB 구축 (05/02 ~ 05/03)

| 항목 | 내용 | 상태 |
|------|------|------|
| 법령 ETL 파이프라인 | Korean Law MCP 7단계 추출 | ✅ 완료 |
| legal_source_registry.json | 37개 seed 항목 (Group A~F) 수집 | ✅ 완료 |
| Legal DB (SQLite) | legal_db_v0_1_3.sqlite (397KB) | ✅ 완료 |
| 법령 체계도 (law_hierarchy) | 법률→시행령→시행규칙→예규→고시 계층 구조 | ✅ 완료 |
| 법령 관계 매핑 | legal_relation_seed_by_jurisdiction | ✅ 완료 |
| 법령 업데이트 파이프라인 | Diff Engine + Update Manifest | ✅ 완료 |
| Item Eligibility 스키마 | 중기경쟁제품·직접생산확인 3단계 정책 | ✅ 완료 |
| No-Mutation Policy | Phase 7 Baseline 동결 정책 | ✅ 완료 |

### Phase 8: Gateway + Rule Engine + Company API (05/03 ~ 05/04)

| 항목 | 내용 | 상태 |
|------|------|------|
| Gateway Skeleton | 5개 Resolver (Source, Item, Route, Procedure, Company) | ✅ 완료 |
| Real DB Resolver 연동 | Legal DB에서 실제 데이터 조회 | ✅ 완료 |
| Rule Engine v0.1 | 8단계 우선순위 체계, BDD 테스트 | ✅ 완료 |
| Company API Adapter | mock/live 전환, location post-filtering | ✅ 완료 |
| Forbidden Phrase Re-scan | 후보 테이블 삽입 후 재검사 | ✅ 완료 |
| Poisoned Markdown Fallback | 금지 표현 감지 시 전체 답변 교체 | ✅ 완료 |

### Phase 9: Intent Router + Rule Catalog (05/03 ~ 05/04)

| 항목 | 내용 | 상태 |
|------|------|------|
| Phase 9.1 Rule Mapping | 지역업체 구매지원 법적 규칙 매핑 | ✅ 완료 |
| Phase 9.2-A Rule Catalog v0.2 | 37개 규칙 정밀화, 하드코딩 제거 | ✅ 완료 |
| Phase 9.2-B Source Mapping | DB Source Mapping (Status/Expansion/Numeric) | ✅ 완료 |
| Phase 9.2-C Source Chain Discovery | 랭킹 시스템, rank_score 보정 | ✅ 완료 |
| Phase 9.3 Gemini Intent Router | Gemini JSON 파싱 + Deterministic Validator | ✅ 완료 |
| procurement_route slot 보정 | MAS/종합쇼핑몰/제3자단가 키워드 → slot 자동 채움 | ✅ 완료 |

### Phase 10: Answer Builder + Runtime Orchestrator (05/04 ~ 05/05)

| 항목 | 내용 | 상태 |
|------|------|------|
| Phase 10.2 Answer Type Router v0.2 | 5개 flow (legal/contract/candidate/mixed/clarification) | ✅ 완료 |
| Phase 10.3 Pipeline Integration Test | 9개 flow + forbidden sweep | ✅ 완료 |
| Phase 10.4 Runtime Orchestrator | 7-stage 파이프라인, stage status tracking | ✅ 완료 |
| Phase 10.5 Evidence-Based Answer Builder | source_chain_status별 display_level, numeric gating | ✅ 완료 |

---

## 4. 법령 DB 상세

### 4.1 법령 소스 체계

```
L1 법률 ─┬─ 지방계약법 (법률 제19634호)
         ├─ 국가계약법 (법률 제21420호)
         └─ 조달사업법 (법률 제21420호)

L2 시행령 ─┬─ 지방계약법 시행령 (대통령령 제35947호)
           ├─ 국가계약법 시행령 (대통령령 제35947호)
           └─ 조달사업법 시행령 (대통령령 제35947호)

L3 시행규칙 ─ 지방계약법 시행규칙, 조달사업법 시행규칙

L4 행정규칙 ─┬─ 행안부 예규: 입찰 및 계약집행기준 (제332호)
             ├─ 행안부 예규: 낙찰자 결정기준 (제344호)
             ├─ 조달청 훈령: 내자구매업무 처리규정, MAS 업무처리규정
             ├─ 조달청 고시: 혁신제품 구매 운영 규정 등
             └─ 부산광역시 조례: 지역상품 우선구매 조례

L5 조달관련 문서 ─ MAS 특수조건, 제3자단가 특수조건 등
```

### 4.2 수집 법령 현황

| 그룹 | 대상 | 수량 | 수집 방법 |
|------|------|------|----------|
| Group A | 국가계약법 계열 (법률+시행령+시행규칙) | 6건 | MCP 자동 |
| Group B | 지방계약법 계열 (법률+시행령+시행규칙) | 6건 | MCP 자동 |
| Group C | 행안부 예규 (집행기준+낙찰기준) | 6건 | MCP 자동 |
| Group D | 조달청 훈령/고시 (MAS, 혁신, 우수조달 등) | 10건 | MCP + PDF 수동 |
| Group E | 지방공기업법 계열 | 3건 | MCP 자동 |
| Group F | 부산시 조례, 중기부 고시 등 | 6건 | MCP + 수동 |
| **합계** | | **37건** | |

### 4.3 Legal DB 스키마

```sql
-- legal_db_v0_1_3.sqlite (397KB)
CREATE TABLE legal_sources (...)
CREATE TABLE legal_articles (...)
CREATE TABLE legal_relations (...)
CREATE TABLE item_eligibility (...)
CREATE TABLE sme_competition_products (...)
CREATE TABLE direct_production_requirements (...)
```

### 4.4 Rule Catalog & Source Chain

- **Rule Catalog**: 37개 규칙 (`local_purchase_support_rule_catalog.json`, 60KB)
- **Source Map**: 37개 규칙별 법령 매핑 (`purchase_support_rule_source_map.json`, 179KB)

**Source Chain Status 현황**:

| 상태 | 수량 | 의미 |
|------|------|------|
| `partial_mapped` | 27 | 일부 source 후보 있으나 미완 |
| `mapped_verified` | 2 | 검증 완료 |
| `mapped_candidate` | 2 | 후보 있으나 검토 필요 |
| `pending_resolution` | 2 | 핵심 source 미매핑 |
| `company_api_mapping_required` | 4 | 업체 API 연동 대상 |

---

## 5. 모니터링 시스템 업체 DB 연동

### 5.1 업체 DB 개요

| 항목 | 수치 |
|------|------|
| 부산 소재 업체 수 | 20,000+ |
| 면허 업종 수 | 18,678 |
| 대표 품명 수 | 20,345 |
| 인증제품 데이터 | 112,803건 (4개 도메인 분류) |

### 5.2 API 연동 구조

```
Chatbot Runtime
    │
    ▼
CompanyAPIAdapter (app/runtime/company_api_adapter.py)
    │
    ├── mock mode (기본): 내장 테스트 데이터 반환
    │
    └── live mode: 내부 모니터링 시스템 REST API 호출
         │
         ├── GET /api/chatbot/search?product_name={품목}
         │   → 후보 목록 (company_id, location, 품목 등)
         │
         └── Location Post-Filtering
             → API가 지역 필터 미지원이므로 클라이언트 측 필터링
```

### 5.3 안전 정책

| 정책 | 설명 |
|------|------|
| HMAC-SHA256 | 사업자등록번호 → 해시 기반 비식별 company_id |
| PII 미노출 | 대표자명, 이메일, 사업자등록번호 비노출 |
| 후보 라벨링 | "상태: 검토 후보", "적격 확인 필요" 명시 |
| 금지 표현 검사 | 후보 테이블 삽입 후 재검사 |
| Poisoned Markdown Fallback | 금지 표현 감지 시 전체 답변 안전 문구로 교체 |

---

## 6. 테스트 현황

### 6.1 테스트 파일 목록 (16개 파일, 181건)

| 테스트 파일 | 건수 | 검증 대상 |
|-------------|------|----------|
| test_evidence_policy.py | 13 | display_level 분류, numeric display 판정 |
| test_evidence_context_loader.py | 15 | rule 추론, contract_object 분기, route slot 보정 |
| test_evidence_answer_builder.py | 12 | evidence section 삽입, hint 차단, 금지표현, 금액 보존 |
| test_runtime_evidence_integration.py | 7 | orchestrator 통합, stage lifecycle |
| test_chatbot_runtime_orchestrator.py | 22 | orchestrator 전체 흐름, forbidden rescan |
| test_router_to_answer_integration.py | 11 | Router → Answer 통합 |
| test_answer_type_router.py | 14 | 5개 flow 라우팅, safe wording |
| test_gemini_intent_router.py | 5 | JSON 파싱, confidence fallback |
| test_intent_routing_cases.py | 7 | 8개 시나리오 케이스 |
| test_purchase_support_source_chain_resolver.py | 8 | source chain 37 규칙 |
| test_local_purchase_support_rule_mapping.py | - | rule mapping 검증 |
| test_rule_engine_v0_1.py | - | rule engine BDD |
| test_phase8_gateway_mock_validation.py | - | gateway mock 13건 |
| test_phase8_real_db_smoke.py | - | real DB 연동 smoke |
| test_answer_builder_v0_1.py | - | answer builder 기초 |
| test_v144.py | - | 레거시 검증 (5건 known failure) |

### 6.2 현재 통과 현황

```
Phase 10.5 관련 테스트: 108/108 PASS ✅
전체 테스트 (test_v144 제외): 176/176 PASS ✅
test_v144 (레거시): 5건 known failure (Phase 10.5와 무관)
```
