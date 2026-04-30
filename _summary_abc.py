import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

STATUS_MAP = {
    "mcp_preflight_success": "MCP 최신 확인",
    "cache_refreshed_from_mcp": "MCP로 최신 갱신",
    "cached_verified": "캐시된 확인 근거 사용",
    "no_mcp_required": "법령조회 불필요",
    "mcp_failed_no_basis": "근거 확인 실패, 법적 판단 유보",
}
RAW_TOOLS = ['chain_law_system','chain_procedure_detail','chain_ordinance_compare',
    'chain_full_research','search_law','get_law_text','search_admin_rule','get_admin_rule']

for s in ['a','b','c']:
    data = json.load(open(f'scenario_{s}_raw.json', encoding='utf-8-sig'))
    ans = data.get('answer','')
    ss = data.get('source_status','')
    ssl = data.get('source_status_user_label','')
    leaked = [t for t in RAW_TOOLS if t in ans]
    mcp = data.get('mandatory_mcp_executed',[])
    cache_entries = [e for e in mcp if 'cache_hit' in e]

    print(f'=== {s.upper()} ===')
    print(f'  tier={data.get("tier_resolved")}  builder={data.get("answer_builder_used")}')
    print(f'  source_status={ss}  label={ssl}  expected={STATUS_MAP.get(ss,"?")}  match={ssl==STATUS_MAP.get(ss,"?")}')
    print(f'  table_rendered={data.get("legal_basis_table_rendered")}  table_in_answer={"| 검토 근거 |" in ans}')
    print(f'  leaked={leaked if leaked else "NONE"}  forbidden={data.get("forbidden_patterns_remaining_after_rewrite")}')
    print(f'  cache_hit_count={data.get("legal_basis_cache_hit_count")}  cache_entries={len(cache_entries)}')
    print(f'  builder_elapsed={data.get("answer_builder_elapsed_ms")}ms  net_calls={data.get("answer_builder_network_call_count")}')
    print(f'  latency={data.get("latency_ms")}ms')
    if cache_entries and '| 검토 근거 |' in ans:
        print(f'  per_row_cache: {"PASS" if "캐시된 확인 근거 사용" in ans else "FAIL"}')
    print(f'  cache_notice: {"PASS" if "캐시로 재사용" in ans else "N/A (no cache_hit)" if not cache_entries else "FAIL"}')
    # Show answer first 400 chars
    print(f'  answer_head: {ans[:400].replace(chr(10),"\\n")}')
    print()
