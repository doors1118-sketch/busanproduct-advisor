import json

d = json.load(open(r'app\data\legal_source_registry.json', 'r', encoding='utf-8'))

# 전체 필드에서 MCP 에러 포함 여부 확인
errs = []
for r in d:
    has_err = False
    for field in ['raw_search_result_preview', 'law_system_tree', 'annexes', 'amendment_history', 'citations_verified']:
        val = r.get(field, '') or ''
        if 'MCP 호출 오류' in val:
            has_err = True
            break
    if has_err:
        errs.append(r['seed_id'])

print(f"에러 텍스트가 데이터에 저장된 Seed: {len(errs)}건")
for sid in errs:
    print(f"  - {sid}")
