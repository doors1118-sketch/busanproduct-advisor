# TEST_RESULTS.md

## 1. 테스트 실행 요약
- **실행 명령어**: `python -m unittest tests.test_v144 -v`
- **전체 테스트 개수**: 31개
- **통과 개수**: 31개
- **실패 개수**: 0개
- **실패 원인**: 해당사항 없음
- **Mock 사용 여부**: 예 (Gemini API 모델, RAG 검색, 외부 API 등에 Mock 객체 사용)
- **실제 API 사용 여부**: 아니오 (모든 테스트는 로컬 단위 테스트로 외부 의존성을 제거하고 수행됨)
- **테스트 실행 시점**: 2026-04-25T22:42 KST 기준

## 2. 세부 검증 항목 (필수 포함 테스트)

| 테스트 클래스 / 메서드 | 상태 | 검증 내용 |
|---|---|---|
| `TestPromptAssembler` | | **프롬프트 조립기 로직 검증** |
| `test_core_prompt_hash_stable_across_questions` | ✅ Pass | 다른 질문이 들어와도 Core Prompt(0번 블록)의 해시는 불변임을 보장함. |
| `test_core_prompt_is_block_zero` | ✅ Pass | Core Prompt가 `system_instruction`에만 주입되며 첫 번째 블록에 위치함. |
| `test_date_instruction_not_in_core` | ✅ Pass | 조회 시점과 같은 가변 정보(Date)가 Core가 아닌 Dynamic Context 영역에 위치함. |
| `test_dynamic_guardrail_not_inserted_before_core` | ✅ Pass | Guardrail 컨텐츠가 Core 블록에 섞이지 않고 엄격히 분리됨. |
| `test_prompt_injection_ignore_guardrail` | ✅ Pass | (승인 추가 테스트) 사용자가 가드레일 무시 요청을 해도 방어 문장이 적용됨. |
| | | |
| `TestRouting` | | **3단계 라우팅 검증** |
| `test_company_search_forced` | ✅ Pass | 업체명/사업자번호 등의 키워드 인식 시 `company_search` 가드레일 선택됨. |
| `test_fast_path_not_used_for_mixed_keywords` | ✅ Pass | (승인 추가 테스트) 다의어/혼합계약 포함 시 fast path를 건너뛰고 정상 라우팅됨. |
| `test_item_purchase_single` | ✅ Pass | 단일 유형(물품)의 명확한 질문인 경우 정확히 fast path를 타는지 검증. |
| | | |
| `TestVerifyAndAnnotate` | | **환각 검증 및 보정** |
| `test_verify_and_annotate_downgrades_unverified_citation` | ✅ Pass | (승인 추가 테스트) `legal_basis`에 존재하지 않는 조문 인용 시 `[최신 법령 확인 완료]` 태그를 `[확인 필요]`로 자동 강등시킴. |
| `test_verify_annotate_law_name_plus_article` | ✅ Pass | 법령명과 조문(예: 지방계약법 제25조 vs 국가계약법 제25조)을 맵핑하여 오판하지 않음. (P0-9 검증) |
| | | |
| `TestLegalScope` | | **타임아웃 및 결론 제어 검증** |
| `test_legal_scope_blocks_final_answer` | ✅ Pass | 핵심 도구 실패 시 `blocked_scope`가 발생하여 확정적 답변 생성을 금지함. |
| `test_precedent_timeout_allows_law_conclusion` | ✅ Pass | 단순 판례 검색 타임아웃은 일반적인 법적 결론 생성을 완전히 차단하지 않음을 확인함. |
| | | |
| `TestP0Fixes` | | **P0 수정사항 회귀 테스트** |
| `test_agency_type_mapping_to_prompt_assembler_keys` | ✅ Pass | 사이드바 기관유형과 내부 Mapper의 Key가 정확히 일치함. |
| `test_chat_v144_rag_context_contains_values_not_keys` | ✅ Pass | RAG 조립 시 딕셔너리의 Key가 아닌 Value가 올바르게 결합됨. |
| `test_chat_v144_uses_company_policy_formatter` | ✅ Pass | 레거시가 아닌 `company_policy.format_company_for_llm` 포매터가 사용됨. |
| `test_company_api_no_hardcoded_key` | ✅ Pass | 하드코딩된 국세청/공공데이터 포털 API Key가 제거됨. |
| `test_mcp_client_env_names_match_env_example` | ✅ Pass | `.env`의 `MCP_ENDPOINT` 및 `LAW_OC`와 `mcp_client.py`의 Fallback 처리가 일치함. |
| `test_prompt_prefix_hash_logged` | ✅ Pass | `prompt_prefix_hash` 속성이 존재하며 라우팅 로그를 통해 기록됨. |
| `test_timeout_policy_used_in_execute_function_call` | ✅ Pass | 하드코딩된 타임아웃 대신 `policies.timeout_policy.get_timeout()`을 호출함. |
| | | |
| `TestMonitoring` | | **모니터링 및 로깅 정책** |
| `test_redact_business_number` | ✅ Pass | 사업자번호가 올바르게 PII 마스킹 처리됨. |
| `test_redact_email` | ✅ Pass | 이메일 주소가 PII 마스킹 처리됨. |
| `test_redact_phone` | ✅ Pass | 전화번호가 PII 마스킹 처리됨. |
| | | |
| `TestFeatureFlag` | | **기능 플래그 검증** |
| `test_legacy_mode_uses_system_prompt` | ✅ Pass | `PROMPT_MODE=legacy` 설정 시 기존 `system_prompt` 모듈을 정상적으로 사용함. |
| `test_dynamic_mode_env` | ✅ Pass | `PROMPT_MODE=dynamic_v1_4_4` 설정 시 동적 프롬프트 조립기가 동작함. |

> 모든 필수 테스트 항목이 통과되었으며 `P0` 수정 피드백이 코드에 온전히 반영되었음을 검증했습니다.
