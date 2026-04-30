import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

FIELDS = [
    "tier_resolved", "answer_builder_used", "answer_sections_rendered",
    "candidate_section_position", "legal_basis_section_rendered",
    "user_facing_source_labels_used", "raw_tool_names_hidden_from_answer",
    "legal_basis_table_rendered", "legal_basis_to_purchase_route_mapped",
    "source_status_user_label", "candidate_table_source",
    "forbidden_patterns_remaining_after_rewrite",
    "deterministic_template_used", "latency_ms",
    "mandatory_mcp_executed", "mandatory_mcp_missing",
    "legal_basis_cache_used", "legal_basis_cache_hit_count",
]

RAW_TOOLS = [
    'chain_law_system', 'chain_procedure_detail', 'chain_ordinance_compare',
    'chain_full_research', 'search_law', 'get_law_text',
    'search_admin_rule', 'get_admin_rule'
]

for s in ['a', 'b']:
    data = json.load(open(f'scenario_{s}_raw.json', encoding='utf-8-sig'))
    ans = data.get('answer', '')
    leaked = [t for t in RAW_TOOLS if t in ans]
    has_table = '| 검토 근거 |' in ans

    print(f'\n{"="*60}')
    print(f'=== Scenario {s.upper()} ===')
    print(f'{"="*60}')
    print()
    print('[Metadata]')
    for field in FIELDS:
        val = data.get(field)
        if isinstance(val, (list, dict)):
            print(f'  {field}: {json.dumps(val, ensure_ascii=False)}')
        else:
            print(f'  {field}: {val}')

    print()
    print('[Phase 5 Compliance]')
    if leaked:
        print(f'  raw_tool_name_leaked: {leaked}')
    else:
        print(f'  raw_tool_name_leaked: NONE - PASS')
    print(f'  legal_basis_table_in_answer: {has_table}')
    print()
    print('[Answer Full Text]')
    print(ans)
    print()
