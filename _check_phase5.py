import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

RAW_TOOL_NAMES = [
    'chain_law_system', 'chain_procedure_detail', 'chain_ordinance_compare',
    'chain_full_research', 'search_law', 'get_law_text',
    'search_admin_rule', 'get_admin_rule', 'chain_action_basis',
    'search_interpretations', 'chain_document_review'
]

for s in ['a', 'b', 'd']:
    try:
        data = json.load(open(f'scenario_{s}_raw.json', encoding='utf-8-sig'))
    except:
        print(f'=== Scenario {s.upper()} === MISSING')
        continue

    ans = data.get('answer', '')
    print(f'\n=== Scenario {s.upper()} ===')
    print(f'tier: {data.get("tier_resolved")}')
    print(f'builder: {data.get("answer_builder_used")}')
    print(f'legal_basis_table_rendered: {data.get("legal_basis_table_rendered")}')
    print(f'raw_tool_names_hidden: {data.get("raw_tool_names_hidden_from_answer")}')
    print(f'user_facing_source_labels_used: {data.get("user_facing_source_labels_used")}')
    print(f'mandatory_mcp_executed: {json.dumps(data.get("mandatory_mcp_executed"), ensure_ascii=False)}')

    leaked = []
    for t in RAW_TOOL_NAMES:
        if t in ans:
            idx = ans.index(t)
            leaked.append(t)
            ctx = ans[max(0, idx-50):idx+len(t)+50].replace('\n', '\\n')
            print(f'  LEAKED: {t}')
            print(f'    context: ...{ctx}...')

    if not leaked:
        print('  No raw tool name leaks found.')

    # Check if legal basis table is in answer
    if '| 검토 근거 |' in ans:
        print('  Legal basis table: PRESENT in answer')
    else:
        print('  Legal basis table: MISSING from answer')

    print(f'  Answer first 300 chars:')
    print(f'    {ans[:300].replace(chr(10), "\\n")}')
