import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FIELDS = [
    "tier_resolved", "answer_builder_used", "answer_sections_rendered",
    "candidate_section_position", "legal_basis_section_rendered",
    "user_facing_source_labels_used", "raw_tool_names_hidden_from_answer",
    "legal_basis_table_rendered", "legal_basis_to_purchase_route_mapped",
    "source_status", "source_status_user_label", "candidate_table_source",
    "forbidden_patterns_remaining_after_rewrite",
    "deterministic_template_used", "latency_ms",
    "mandatory_mcp_executed", "mandatory_mcp_missing",
    "legal_basis_cache_used", "legal_basis_cache_hit_count",
    "answer_builder_elapsed_ms", "answer_builder_network_call_count",
]
RAW_TOOLS = [
    'chain_law_system', 'chain_procedure_detail', 'chain_ordinance_compare',
    'chain_full_research', 'search_law', 'get_law_text',
    'search_admin_rule', 'get_admin_rule', 'chain_action_basis',
]
STATUS_MAP = {
    "mcp_preflight_success": "MCP 최신 확인",
    "cache_refreshed_from_mcp": "MCP로 최신 갱신",
    "cached_verified": "캐시된 확인 근거 사용",
    "no_mcp_required": "법령조회 불필요",
    "mcp_failed_no_basis": "근거 확인 실패, 법적 판단 유보",
}

for s in ['a', 'b', 'c', 'd']:
    try:
        data = json.load(open(f'scenario_{s}_raw.json', encoding='utf-8-sig'))
    except Exception as e:
        print(f'\n=== Scenario {s.upper()} === ERROR: {e}')
        continue
    ans = data.get('answer', '')
    leaked = [t for t in RAW_TOOLS if t in ans]
    has_table = '| 검토 근거 |' in ans
    has_cache_notice = '캐시로 재사용' in ans
    ss = data.get('source_status', '')
    ssl = data.get('source_status_user_label', '')
    expected_ssl = STATUS_MAP.get(ss, '?')
    ssl_match = ssl == expected_ssl

    print(f'\n{"="*60}')
    print(f'=== Scenario {s.upper()} ===')
    print(f'{"="*60}')
    print('[Metadata]')
    for f in FIELDS:
        v = data.get(f)
        if isinstance(v, (list, dict)):
            print(f'  {f}: {json.dumps(v, ensure_ascii=False)}')
        else:
            print(f'  {f}: {v}')
    print()
    print('[Phase 5 Step 2 Compliance]')
    print(f'  raw_tool_leaked: {"FAIL: " + str(leaked) if leaked else "PASS"}')
    print(f'  legal_basis_table_in_answer: {has_table}')
    print(f'  cache_notice_in_answer: {has_cache_notice}')
    print(f'  source_status_user_label_matches: {ssl_match} (got="{ssl}", expected="{expected_ssl}")')
    print(f'  answer_builder_network_call_count: {data.get("answer_builder_network_call_count", "?")}')
    print(f'  answer_builder_elapsed_ms: {data.get("answer_builder_elapsed_ms", "?")}')
    # cache_hit per-row check
    mcp_exec = data.get('mandatory_mcp_executed', [])
    cache_entries = [e for e in mcp_exec if 'cache_hit' in e]
    if cache_entries:
        print(f'  cache_hit_entries: {len(cache_entries)}')
        if has_table:
            print(f'  per_row_cache_status: {"PASS" if "캐시된 확인 근거 사용" in ans else "FAIL - missing per-row cache status"}')
    print()
    print('[Answer Full Text]')
    print(ans)
    print()
