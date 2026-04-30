import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import os
os.environ.setdefault("PYTHONPATH", ".;app")
sys.path.insert(0, ".")
sys.path.insert(0, "app")

from app.gemini_engine import chat, get_last_generation_meta

queries = {
    'A': '7천만원으로 컴퓨터 구매해야 한다. 가급적 지역업체랑 계약하고 싶은데 방법이 있을까?',
    'B': '8천만원 물품 수의계약 가능해?',
    'D': 'CCTV 부산업체 추천해줘'
}

RAW_TOOLS = [
    'chain_law_system', 'chain_procedure_detail', 'chain_ordinance_compare',
    'chain_full_research', 'search_law', 'get_law_text',
    'search_admin_rule', 'get_admin_rule'
]

for label, q in queries.items():
    print(f'\n=== Scenario {label} ===')
    ans, hist = chat(q)
    meta = get_last_generation_meta()

    tier = meta.get('tier_resolved')
    builder = meta.get('answer_builder_used')
    table_rendered = meta.get('legal_basis_table_rendered')
    raw_hidden = meta.get('raw_tool_names_hidden_from_answer')
    source_labels = meta.get('user_facing_source_labels_used')
    cand_source = meta.get('candidate_table_source')
    forbidden = meta.get('forbidden_patterns_remaining_after_rewrite')

    leaked = [t for t in RAW_TOOLS if t in ans]
    has_table = '| 검토 근거 |' in ans

    print(f'  tier: {tier}')
    print(f'  builder: {builder}')
    print(f'  table_rendered: {table_rendered}')
    print(f'  raw_hidden: {raw_hidden}')
    print(f'  source_labels: {source_labels}')
    print(f'  candidate_table_source: {cand_source}')
    print(f'  forbidden: {forbidden}')
    print(f'  leaked_tools: {leaked}')
    print(f'  basis_table_in_answer: {has_table}')
    print(f'--- ANSWER (first 600 chars) ---')
    print(ans[:600])
    print('--- END ---')
