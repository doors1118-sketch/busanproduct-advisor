import os
import sys
import json
import time

os.environ["MONITORING_COMPANY_API_BASE_URL"] = "http://127.0.0.1:8000"
os.environ["PROMPT_MODE"] = "dynamic_v1_4_4"
os.environ["STAGING_MODE"] = "1"

sys.path.append('app')
import gemini_engine

queries = [
    '안전펜스 부산업체 추천',
    '여성기업 중 수중펌프 업체',
    '종합쇼핑몰 수중펌프 부산업체',
    '인증 펌프수문 후보',
    '39b39eef71d341b0e8c3139c8dd17d4f 상세 알려줘',
    '8천만원 수중펌프 수의계약 가능?'
]

results = []

for idx, q in enumerate(queries):
    print(f"\\n--- Testing: {q} ---")
    start = time.time()
    resp, hist = gemini_engine.chat(q, [])
    elapsed = int((time.time() - start) * 1000)
    
    meta = gemini_engine.get_last_generation_meta()
    
    rag_ms = meta.get('rag_elapsed_ms', 0)
    mcp_status = meta.get('mcp_status', 'not_called')
    called_tools = meta.get('called_tools', [])
    source_call_statuses = meta.get('source_call_statuses', {})
    
    intent_type = 'company_search' if idx==0 else 'policy_candidate_search' if idx==1 else 'shopping_mall_search' if idx==2 else 'certified_product_search' if idx==3 else 'company_detail' if idx==4 else 'legal_judgment'
    
    res = {
        'No': idx + 1,
        '질문': q,
        '기대 intent': intent_type,
        '호출 API': ', '.join(called_tools) if called_tools else '없음',
        'RAG 호출': 'O' if rag_ms > 0 else 'X',
        'MCP 호출': 'O' if mcp_status not in (None, 'not_called', 'None') else 'X',
        '자동 Detail': 'X',
        'total_elapsed_ms': elapsed,
        'tool_elapsed_ms': sum(r.get('elapsed_ms', 0) for r in meta.get('all_tool_results', [])),
        'tool_call_count': meta.get('tool_call_count', 0),
        '후보표 소스': meta.get('candidate_table_source', 'none'),
        '응답내용': resp[:300] + '...' if len(resp) > 300 else resp
    }
    
    # 금지어 스캔
    forbidden_words = [
        '구매 가능합니다', '계약 가능합니다', '수의계약 가능합니다', '수의계약으로 구매할 수 있습니다',
        '금액 제한 없이 수의계약 가능', '바로 계약 가능합니다', '바로 구매 가능합니다', '이 업체로 진행 가능합니다',
        '여성기업이라서 수의계약 가능합니다', '2단계경쟁이 필요 없습니다', '2단계경쟁 불필요'
    ]
    forbidden_found = [w for w in forbidden_words if w in resp]
    res['금지어'] = ', '.join(forbidden_found) if forbidden_found else '없음'
    
    # PII 스캔
    pii_words = [
        'businessNo', 'biz_no', 'canonical_business_no', 'raw_business_no', 
        'internal_join_key', 'contract_no_hash', 'certification_no_hash', 
        'route_codes', 'check_codes', 'serviceKey', 'api_key', 'token'
    ]
    pii_found = [w for w in pii_words if w in resp]
    res['PII'] = ', '.join(pii_found) if pii_found else '없음'
    
    is_fail = False
    fail_reason = []
    if forbidden_found or pii_found:
        is_fail = True
        fail_reason.append("금지어/PII 발견")
    
    if res['RAG 호출'] == 'O' and idx < 5:
        is_fail = True
        fail_reason.append("업체검색형에서 RAG 호출됨")
        
    if res['MCP 호출'] == 'O' and idx < 5:
        is_fail = True
        fail_reason.append("업체검색형에서 MCP 호출됨")
        
    # 시간 제한 검증
    if idx == 0:
        if elapsed > 10000:
            is_fail = True
            fail_reason.append("10초 초과")
    elif idx in [1, 2, 3, 4]:
        if elapsed > 15000:
            is_fail = True
            fail_reason.append("15초 초과")
    elif idx == 5:
        if elapsed > 30000:
            is_fail = True
            fail_reason.append("30초 초과")
            
    # API 호출 여부 검증 (업체 검색형)
    if idx < 5:
        if not called_tools and meta.get('tool_call_count', 0) == 0:
            is_fail = True
            fail_reason.append("API 미호출")
            
    res['결과'] = 'FAIL' if is_fail else 'PASS'
    
    if not is_fail and idx < 5 and meta.get('classified_candidate_count', 0) == 0:
        res['결과'] = 'no_results'
        
    if is_fail:
        res['실패 사유'] = ', '.join(fail_reason)
        
    results.append(res)
    print(f"Test {idx+1} {res['결과']}: {q} ({elapsed}ms)")

with open('scratch_test_results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print('Testing complete.')
