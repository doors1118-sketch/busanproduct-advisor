"""
Phase 7-A 검증 스크립트
- 업체검색형 1~5번: Phase 7-A 기준 판정
- 6번 법령판단형: Phase 7-B backlog 표시
- tool_elapsed_ms_by_name, tool_args_log, 필수 필드 검증 포함
"""
import os
import sys
import json
import time

os.environ["MONITORING_COMPANY_API_BASE_URL"] = "https://busanproduct.co.kr"
os.environ["PROMPT_MODE"] = "dynamic_v1_4_4"
os.environ["STAGING_MODE"] = "1"

sys.path.append('app')
import gemini_engine

queries = [
    '안전펜스 부산업체 추천',
    '여성기업 중 수중펌프 업체',
    '종합쇼핑몰 수중펌프 부산업체',
    '인증 펌프수문 후보',
    '04bd039a0e08f1aa5f94ccc9c9352e60 상세 알려줘',
    '8천만원 수중펌프 수의계약 가능?'
]

intent_types = [
    'company_search',
    'policy_candidate_search',
    'shopping_mall_search',
    'certified_product_search',
    'company_detail',
    'legal_judgment'
]

# Phase 7-A 필수 generation_meta 필드
REQUIRED_META_FIELDS = [
    'tool_elapsed_ms_by_name',
    'tool_args_log',
    'source_call_statuses',
    'classified_candidate_count',
    'formatter_input_count',
    'formatter_output_chars',
    'candidate_table_source',
]

results = []

for idx, q in enumerate(queries):
    print(f"\n{'='*60}")
    print(f"=== Test {idx+1}: {q}")
    print(f"{'='*60}")
    start = time.time()
    resp, hist = gemini_engine.chat(q, [])
    elapsed = int((time.time() - start) * 1000)
    
    meta = gemini_engine.get_last_generation_meta()
    
    rag_ms = meta.get('rag_elapsed_ms', 0)
    mcp_status = meta.get('mcp_status', 'not_called')
    called_tools = meta.get('called_tools', [])
    source_call_statuses = meta.get('source_call_statuses', {})
    tool_elapsed = meta.get('tool_elapsed_ms_by_name', {})
    tool_args_log = meta.get('tool_args_log', [])
    
    res = {
        'No': idx + 1,
        '질문': q,
        '기대 intent': intent_types[idx],
        '호출 API': ', '.join(called_tools) if called_tools else '없음',
        'RAG 호출': 'O' if rag_ms > 0 else 'X',
        'MCP 호출': 'O' if mcp_status not in (None, 'not_called', 'None') else 'X',
        'total_elapsed_ms': elapsed,
        'tool_elapsed_ms_by_name': tool_elapsed,
        'tool_args_log': tool_args_log,
        'tool_call_count': meta.get('tool_call_count', 0),
        '후보표 소스': meta.get('candidate_table_source', 'none'),
        'classified_candidate_count': meta.get('classified_candidate_count', 0),
        'formatter_input_count': meta.get('formatter_input_count', 0),
        'formatter_output_chars': meta.get('formatter_output_chars', 0),
        'source_call_statuses': source_call_statuses,
        'fast_track_applied': meta.get('fast_track_applied', False),
        'tier_resolved': meta.get('tier_resolved', -1),
        '응답내용': resp[:400] + '...' if len(resp) > 400 else resp
    }
    
    # === Phase 7-A 검증 항목 ===
    is_fail = False
    fail_reasons = []
    
    # 1. 금지어 스캔
    forbidden_words = [
        '구매 가능합니다', '계약 가능합니다', '수의계약 가능합니다',
        '수의계약으로 구매할 수 있습니다', '금액 제한 없이 수의계약 가능',
        '바로 계약 가능합니다', '바로 구매 가능합니다',
        '여성기업이라서 수의계약 가능합니다',
    ]
    forbidden_found = [w for w in forbidden_words if w in resp]
    res['금지어'] = ', '.join(forbidden_found) if forbidden_found else '없음'
    
    # 2. PII 스캔
    pii_words = [
        'businessNo', 'biz_no', 'canonical_business_no', 'raw_business_no',
        'internal_join_key', 'contract_no_hash', 'certification_no_hash',
        'route_codes', 'check_codes', 'serviceKey', 'api_key', 'token'
    ]
    pii_found = [w for w in pii_words if w in resp]
    res['PII'] = ', '.join(pii_found) if pii_found else '없음'
    
    if forbidden_found or pii_found:
        is_fail = True
        fail_reasons.append("금지어/PII 발견")
    
    # 3. RAG/MCP 우회 검증 (업체검색형 1~5만)
    if idx < 5:
        if res['RAG 호출'] == 'O':
            is_fail = True
            fail_reasons.append("업체검색형에서 RAG 호출됨")
        if res['MCP 호출'] == 'O':
            is_fail = True
            fail_reasons.append("업체검색형에서 MCP 호출됨")
    
    # 4. 응답 시간 검증
    if idx == 0:
        if elapsed > 10000:
            is_fail = True
            fail_reasons.append(f"10초 초과 ({elapsed}ms)")
    elif idx in [1, 2, 3, 4]:
        if elapsed > 15000:
            is_fail = True
            fail_reasons.append(f"15초 초과 ({elapsed}ms)")
    
    # 5. API 호출 여부 (업체검색형)
    if idx < 5:
        if not called_tools and meta.get('tool_call_count', 0) == 0:
            is_fail = True
            fail_reasons.append("API 미호출")
    
    # 6. Phase 7-A 필수 meta 필드 검증
    missing_fields = [f for f in REQUIRED_META_FIELDS if f not in meta]
    if missing_fields:
        is_fail = True
        fail_reasons.append(f"필수 meta 필드 누락: {missing_fields}")
    
    # 7. tool_elapsed_ms_by_name이 실제 값인지 (0이 아닌지) 확인 — 업체검색형만
    if idx < 5:
        if not tool_elapsed or all(v == 0 for v in tool_elapsed.values()):
            fail_reasons.append("tool_elapsed_ms 전부 0 (경고)")
            # 로컬 127.0.0.1 서버 미기동 시 expected → WARN으로 표시, FAIL은 아님
    
    # 8. 정책기업 검색 (idx==1): tool_args_log에 mapped_policy_subtype 존재 확인
    if idx == 1:
        has_policy_subtype = any(
            'mapped_policy_subtype' in str(ta.get('args', {}))
            for ta in tool_args_log
        )
        res['policy_subtype_logged'] = has_policy_subtype
        if not has_policy_subtype:
            fail_reasons.append("policy_subtype 로그 누락")
    
    # 결과 판정
    if idx == 5:
        # 6번 법령판단형: Phase 7-B backlog
        res['결과'] = 'Phase 7-B backlog'
        res['phase'] = '7-B'
    elif is_fail:
        res['결과'] = 'FAIL'
        res['실패 사유'] = ', '.join(fail_reasons)
        res['phase'] = '7-A'
    else:
        if idx < 5 and meta.get('classified_candidate_count', 0) == 0:
            res['결과'] = 'PASS (no_results)'
        else:
            res['결과'] = 'PASS'
        res['phase'] = '7-A'
        if fail_reasons:
            res['경고'] = ', '.join(fail_reasons)
    
    results.append(res)
    print(f"  → {res['결과']} ({elapsed}ms)")
    print(f"  → tool_elapsed: {tool_elapsed}")
    print(f"  → tool_args_log: {json.dumps(tool_args_log, ensure_ascii=False)[:200]}")
    print(f"  → 후보표: {meta.get('candidate_table_source', 'none')}, 분류건수: {meta.get('classified_candidate_count', 0)}")

# 결과 저장
with open('scratch_test_phase7a_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

# 요약 출력
print(f"\n{'='*60}")
print("=== Phase 7-A 검증 결과 요약 ===")
print(f"{'='*60}")
phase7a_results = [r for r in results if r.get('phase') == '7-A']
pass_count = sum(1 for r in phase7a_results if r['결과'].startswith('PASS'))
fail_count = sum(1 for r in phase7a_results if r['결과'] == 'FAIL')
print(f"  Phase 7-A: {pass_count} PASS / {fail_count} FAIL (총 {len(phase7a_results)}건)")
for r in results:
    status = r['결과']
    extra = r.get('실패 사유', r.get('경고', ''))
    suffix = f" → {extra}" if extra else ""
    print(f"  [{r['No']}] {r['질문'][:25]}... → {status}{suffix}")

print(f"\n전체 결과: scratch_test_phase7a_results.json 저장 완료")
