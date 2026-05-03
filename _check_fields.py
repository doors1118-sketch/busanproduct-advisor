import json

d = json.load(open(r'app\data\legal_source_registry.json', 'r', encoding='utf-8'))

fields = ['raw_search_result_preview', 'law_system_tree', 'annexes', 'amendment_history', 'citations_verified']

for r in d[:3]:  # Group A 샘플 3건
    sid = r['seed_id']
    print(f"\n=== {sid} ===")
    for f in fields:
        val = r.get(f, '') or ''
        has_err = 'MCP 호출 오류' in val
        has_data = len(val) > 50 and not has_err
        status = "ERROR" if has_err else ("OK" if has_data else "EMPTY")
        print(f"  {f}: {status} ({len(val)} chars)")
        if has_data:
            print(f"    → {val[:80]}...")
