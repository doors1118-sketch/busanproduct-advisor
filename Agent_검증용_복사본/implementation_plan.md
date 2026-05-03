# 지역업체 DB 연동 (Phase 7-A) 라우터 보완 및 검증 계획 (최종)

사용자님의 지적사항을 완벽히 수용하여, 업체검색형 질문들이 RAG/MCP 호출 없이 즉시(deterministic) 내부 API로 직행하도록 `gemini_engine.py`와 `model_routing_policy.py`의 구조를 전면 수정하고 검증 스크립트를 고도화합니다.

## 1. 수정 대상 및 방향

### 1-1. `app/policies/model_routing_policy.py` 수정
- `classify_query_tier` 함수 내에서 Tier 0 (Fast-track) 판단 기준을 대폭 확장합니다.
- 기존에는 `company_search`만 Tier 0으로 처리했으나, 이제 다음 Intent가 포함되어 있고 법령/계약 판단이 필요하지 않은 경우 모두 Tier 0으로 분류되게 합니다.
  - `company_search`
  - `policy_candidate_search`
  - `shopping_mall_search`
  - `certified_product_search`
  - `company_detail`

### 1-2. `app/gemini_engine.py` 수정
- **Fast-Track 위치 이동**: `_parallel_rag_search` 진입 전에 `query_tier == 0` 여부를 판단하고 즉시 return 하여, RAG를 완전히 Bypass합니다.
- `_execute_tier_0_fast_track` 함수를 전면 개편합니다.
- 파악된 `intent_labels`에 따라 다음 도구 조합을 동적으로 매핑하여 직접(`MockFunctionCall` 사용) 실행합니다.
  - `company_search` → `search_company_by_product`
  - `policy_candidate_search` → `search_company_by_policy` 와 `search_company_by_product`를 호출 후, **company_id 교집합(Intersection)**을 우선적으로 병합.
  - `shopping_mall_search` → `search_shopping_mall_product`
  - `certified_product_search` → 키워드 분기 (혁신제품 → `search_innovation_product`, 우수조달 → `search_excellent_procurement_product`, 일반 인증 → `search_certified_product`)
  - `company_detail` → 정규식으로 32자리 UUID(`company_id`)가 추출될 때만 `get_company_detail` 호출. (추출 불가 시 `search_company_by_product` 등으로 Fallback).
- Legacy 도구명 호출을 완전히 배제하고 표준명(`search_company_...`)만을 사용합니다.
- Fast-track 처리 완료 시, LLM의 개입 없이 `candidate_formatter`를 통해 직접 후보표를 렌더링하고 `generation_meta`에 아래 필드를 반드시 포함합니다.
  - `called_tools`
  - `source_call_statuses`
  - `company_search_status`
  - `candidate_table_source`
  - `classified_candidate_count`
  - `formatter_output_chars`
  - `mcp_status='not_called'`, `rag_elapsed_ms=0`

### 1-3. 테스트 스크립트(`scratch_test.py`) 고도화
- `meta.get('api_called')` 대신 `meta.get('called_tools', [])` 및 `source_call_statuses`를 출력하도록 수정합니다.
- **응답시간 기준에 따른 FAIL (Fallback 포함)**:
  - 업체검색형: 10초 초과 시 FAIL
  - 정책기업/쇼핑몰/인증검색/상세조회: 15초 초과 시 FAIL
  - 법령판단형: 30초 초과 시 FAIL
- **후보표 검증 로직**:
  - 업체검색형에서 API 호출이 없고 후보표가 비어 있으면 PASS가 아니라 **FAIL**.
  - API 호출 성공 후 후보 0건인 경우만 `no_results` 판정 (응답 내용은 통과이나 후보가 없음을 기록).

## 2. 검증 계획

- 수정 후, 터미널 환경변수(`PROMPT_MODE=dynamic_v1_4_4`, `STAGING_MODE=1`, `MONITORING_COMPANY_API_BASE_URL=http://127.0.0.1:8000`)를 켠 상태로 `python scratch_test.py`를 재실행합니다.
- 제시된 6개 질문 세트가 각각 의도된 Fast-track 경로를 타고 내부 API(만) 호출하여 후보군을 출력하는지, RAG를 완전히 Bypass 하는지, 응답속도가 10~15초 이내에 완료되는지 스캔합니다.
- 최종 결과를 `walkthrough.md`에 투명하게 작성하여 제출합니다.
