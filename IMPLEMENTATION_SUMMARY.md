# IMPLEMENTATION_SUMMARY.md
## v1.4.4 지역상품 구매확대 챗봇 — 동적 프롬프트 조립 구현 요약

---

## 1. 새로 만든 파일 목록 (21개)

### 프롬프트 파일
| 파일 | 역할 |
|---|---|
| `prompts/core.md` | Core Prompt — 캐시 고정, injection 방어 포함 |
| `prompts/intent_router.md` | flash 모델 분류 지시 |
| `prompts/guardrails/common_procurement.md` | 공통 구매 가드레일 |
| `prompts/guardrails/item_purchase.md` | 물품 구매 |
| `prompts/guardrails/service_contract.md` | 용역 |
| `prompts/guardrails/construction_contract.md` | 공사 |
| `prompts/guardrails/mas_shopping_mall.md` | MAS/쇼핑몰 |
| `prompts/guardrails/mixed_contract.md` | 혼합계약 |
| `prompts/guardrails/company_search.md` | 업체검색 (policy_tags≠contract_possible) |

### 라우팅·조립 엔진
| 파일 | 역할 |
|---|---|
| `app/prompting/__init__.py` | 패키지 |
| `app/prompting/schemas.py` | 전체 스키마 (CompanyResult, LegalConclusionScope, AssembledPrompt 등) |
| `app/prompting/keyword_pre_router.py` | YAML 기반 1차 키워드 분류 |
| `app/prompting/intent_router.py` | flash LLM 2차 분류 + fast path |
| `app/prompting/guardrail_selector.py` | confidence 기반 가드레일 선택 |
| `app/prompting/guardrail_sanity_check.py` | 라우터 오분류 최종 보정 |
| `app/prompting/prompt_assembler.py` | Core/Dynamic 분리 조립 + prompt_prefix_hash 계산 |

### 정책 모듈
| 파일 | 역할 |
|---|---|
| `app/policies/__init__.py` | 패키지 |
| `app/policies/timeout_policy.py` | MCP timeout + evaluate_legal_scope + get_timeout() |
| `app/policies/company_policy.py` | CompanyResult 구조화 검증 + format_company_for_llm |
| `app/policies/caching_policy.py` | Core hash 무결성 |
| `app/policies/monitoring_policy.py` | PII 마스킹 + APP_ENV별 로그 + prompt_prefix_hash 기록 |
| `app/policies/keyword_dictionary.py` | YAML 키워드 사전 관리 |

### 설정·테스트
| 파일 | 역할 |
|---|---|
| `config/keyword_routes.yaml` | 키워드 맵 외부화 |
| `.env.example` | 환경변수 예시 |
| `tests/test_v144.py` | 31개 단위 테스트 |

---

## 2. 수정한 파일 목록 (4개)

| 파일 | 변경 내용 |
|---|---|
| `app/gemini_engine.py` | `PROMPT_MODE` feature flag, `_chat_v144()`, `_verify_and_annotate_v144()` (법령명+조문 검증), agency_type 매핑 통일, timeout_policy 실적용, company_policy formatter 사용, RAG dict values 조립 |
| `app/system_prompt.py` | DEPRECATED 주석 추가 |
| `app/mcp_client.py` | MCP_ENDPOINT/LAW_OC fallback 환경변수, timeout 환경변수화 |
| `app/company_api.py` | 하드코딩 API 키 제거 → ODCLOUD_API_KEY 환경변수 |

---

## 3. Deprecated 처리 파일

| 파일 | 상태 |
|---|---|
| `app/system_prompt.py` | DEPRECATED. `PROMPT_MODE=legacy`일 때만 사용 |

---

## 4. P0 수정 내역 (Rev.2)

| # | 항목 | 상태 |
|---|---|---|
| P0-1 | company_api.py 하드코딩 API 키 제거 → `ODCLOUD_API_KEY` | ✅ ⚠️ 기존 키 재발급 필요 |
| P0-2 | `.env.example` ↔ `mcp_client.py` 환경변수명 통일 (fallback) | ✅ |
| P0-3 | `_chat_v144()` RAG dict values 조립 | ✅ |
| P0-4 | 업체검색 → `format_company_for_llm()` 사용 | ✅ |
| P0-5 | `_execute_function_call()` timeout → `get_timeout()` | ✅ |
| P0-6 | `mcp_client.py` timeout 환경변수화 | ✅ |
| P0-7 | `_normalize_agency_type()` ↔ `_AGENCY_GUIDE_MAP` 키 통일 | ✅ |
| P0-8 | `prompt_prefix_hash` 필드 + 로그 기록 | ✅ |
| P0-9 | `verify_and_annotate` 법령명+조문 단위 검증 | ✅ |
| P0-10 | 추가 테스트 8개 | ✅ |

---

## 5. 기존 SYSTEM_PROMPT 분리 방식

```
기존: system_prompt.py SYSTEM_PROMPT (814줄, 56KB) → 매 요청마다 전체 주입
변경: Core Prompt (prompts/core.md, ~2.4KB) + 동적 Guardrail (질문별 선택) + Runtime Context
```

Core Prompt = `system_instruction` (불변, 캐시 고정)
Dynamic Context = `user content` 첫 메시지 (가변)

---

## 6. PROMPT_MODE 동작 방식

| 값 | 동작 |
|---|---|
| `legacy` (기본) | 기존 `SYSTEM_PROMPT` 전체 사용 |
| `dynamic_v1_4_4` | 3단 라우팅 → 동적 조립 → Core/Dynamic 분리 |

---

## 7. MCP timeout / fail-closed 처리 방식

- `get_timeout(tool_name)`: 환경변수 기반 도구별 timeout (chain: 12초, law: 10초, decision: 5초 등)
- `_mcp_call()` 기본 timeout도 환경변수 기반 (하드코딩 제거)
- `_execute_function_call()`: `get_timeout()` 사용 (MCP_TIMEOUT=30/90 하드코딩 제거)
- `evaluate_legal_scope()` → `blocked_scope` → 최종 답변 결론 확정 금지

---

## 8. 업체 policy_tags 처리 방식

- `CompanyResult.contract_possible = False` 강제
- `_execute_function_call()`에서 `format_company_for_llm()` 사용 (company_api.format_company_results 미사용)
- 출력: "후보", "추가 확인 필요", "법적 적격성 확인 필요"

---

## 9. 로그 및 개인정보 마스킹

| 환경 | 로그 출력 |
|---|---|
| `APP_ENV=local` | `logs/*.jsonl` (10MB × 5개) |
| `APP_ENV=prod` | `stdout` structured JSON |

PII 마스킹: 사업자번호, 전화번호, 이메일
`prompt_prefix_hash` 라우팅 로그에 기록

---

## 10. 요청 흐름

```
사용자 질문
  → 1단계: Keyword Pre-Router
  → 2단계: LLM Intent Router (또는 fast path skip)
  → 3단계: Guardrail Sanity Check
  → RAG 검색 (dict → law/qa/manual/innovation/tech values 조립)
  → 프롬프트 조립: Core(system_instruction) + Dynamic(user content)
  → Gemini API (MAX_TOOL_CALL_ROUNDS=3, timeout_policy 적용)
  → verify_and_annotate (법령명+조문 단위 검증)
  → blocked_scope 경고 추가
  → 답변 반환
```

---

## 핵심 함수 위치표

| 함수 | 파일 | 역할 |
|---|---|---|
| `keyword_pre_route()` | `app/prompting/keyword_pre_router.py` | 키워드 기반 1차 라우팅 |
| `classify_intent()` | `app/prompting/intent_router.py` | LLM Intent Router (fast path 포함) |
| `select_guardrails()` | `app/prompting/guardrail_selector.py` | Guardrail 선택 |
| `apply_guardrail_sanity_check()` | `app/prompting/guardrail_sanity_check.py` | 라우터 오분류 보정 |
| `assemble_prompt()` | `app/prompting/prompt_assembler.py` | Core + Guardrail + Runtime Context 조립 |
| `get_timeout()` | `app/policies/timeout_policy.py` | 도구별 timeout 반환 |
| `call_mcp_with_timeout()` | `app/policies/timeout_policy.py` | MCP timeout 래퍼 |
| `evaluate_legal_scope()` | `app/policies/timeout_policy.py` | 법적 결론 범위 판단 |
| `normalize_company_result()` | `app/policies/company_policy.py` | 업체 결과 구조화 |
| `validate_company_result()` | `app/prompting/schemas.py` | contract_possible 자동 true 방지 |
| `format_company_for_llm()` | `app/policies/company_policy.py` | LLM 전달용 업체 결과 포맷 |
| `_verify_and_annotate_v144()` | `app/gemini_engine.py` | 법령명+조문 인용 검증 |
| `redact_pii()` | `app/policies/monitoring_policy.py` | 로그 개인정보 마스킹 |

---

## 자체 점검표

| 항목 | 상태 | 비고 |
|---|---|---|
| v1.4.4 전체 프롬프트를 System Prompt에 통째로 넣지 않음 | ✅ 완료 | Core(2.4KB)만 system_instruction |
| Core Prompt가 system_instruction에만 들어감 | ✅ 완료 | |
| dynamic_context가 user content로 분리됨 | ✅ 완료 | |
| Core Prompt가 항상 0번 블록임 | ✅ 완료 | |
| date_instruction이 Core 밖에 있음 | ✅ 완료 | |
| Keyword Pre-Router 구현 | ✅ 완료 | |
| LLM Intent Router 구현 | ✅ 완료 | |
| Guardrail Sanity Check 구현 | ✅ 완료 | |
| Pre-Router fast path 조건 제한 | ✅ 완료 | |
| PROMPT_MODE legacy rollback 가능 | ✅ 완료 | |
| MAX_TOOL_CALL_ROUNDS=3 적용 | ✅ 완료 | |
| MCP timeout wrapper 적용 | ✅ 완료 | timeout_policy.get_timeout() |
| HTTP client timeout 실제 적용 | ✅ 완료 | mcp_client._mcp_call → get_timeout() |
| `evaluate_legal_scope()` 구현 | ✅ 완료 | |
| `blocked_scope`가 최종 답변에 반영됨 | ✅ 완료 | |
| MCP required인데 tool call 없을 때 prefetch/block 처리 | ✅ 완료 | |
| `verify_and_annotate()` 구현 | ✅ 완료 | P0-9: 법령명+조문 단위 |
| `policy_tags`가 `contract_possible`로 자동 승격되지 않음 | ✅ 완료 | |
| RAG보다 MCP 법령 판단 우선 | ✅ 완료 | |
| PII 마스킹 적용 | ✅ 완료 | |
| APP_ENV별 로그 방식 분리 | ✅ 완료 | |
| Golden snapshot 테스트 통과 | ✅ 완료 | |
| timeout 테스트 통과 | ✅ 완료 | |
| company policy 테스트 통과 | ✅ 완료 | |
| company_api.py 하드코딩 키 제거 | ✅ 완료 | ⚠️ 재발급 필요 |
| .env.example ↔ mcp_client 환경변수명 통일 | ✅ 완료 | fallback |
| RAG dict values 조립 | ✅ 완료 | |
| format_company_for_llm 적용 | ✅ 완료 | |
| timeout_policy 실적용 | ✅ 완료 | |
| agency_type 매핑 통일 | ✅ 완료 | |
| prompt_prefix_hash 구현 | ✅ 완료 | |
| verify_and_annotate 법령명+조문 검증 | ✅ 완료 | |
