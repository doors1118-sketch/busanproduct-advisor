import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
d = json.load(open('scenario_a_raw.json', encoding='utf-8-sig'))
print("mandatory_mcp_executed:")
for e in d.get('mandatory_mcp_executed', []):
    has_ch = 'cache_hit' in e
    print(f"  [{'+CH' if has_ch else '  '}] {e}")
print(f"cache_hit_count: {d.get('legal_basis_cache_hit_count')}")
print(f"source_status: {d.get('source_status')}")
print(f"source_status_user_label: {d.get('source_status_user_label')}")
print(f"answer_builder_elapsed_ms: {d.get('answer_builder_elapsed_ms')}")
