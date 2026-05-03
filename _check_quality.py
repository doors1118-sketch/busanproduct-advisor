import json

d = json.load(open(r'app\data\legal_source_registry.json', 'r', encoding='utf-8'))

# Group B 행정규칙 샘플: 지방자치단체 입찰 및 계약집행기준
for r in d:
    if r["seed_id"] == "local_bid_execution":
        print(f"=== {r['name']} ===")
        print(f"source_type: {r['source_type']}")
        print(f"issuing_org: {r.get('issuing_org')}")
        print(f"rule_id: {r.get('rule_id')}")
        print(f"raw_search_preview (300 chars):")
        print(r.get("raw_search_result_preview", "N/A")[:300])
        print(f"\nlaw_system_tree (300 chars):")
        print((r.get("law_system_tree") or "N/A")[:300])
        break

print("\n" + "="*60)

# Group C 신규 법률 샘플: 여성기업지원법
for r in d:
    if r["seed_id"] == "women_enterprise_act":
        print(f"=== {r['name']} ===")
        print(f"source_type: {r['source_type']}")
        print(f"mst: {r.get('mst')}")
        print(f"raw_search_preview (300 chars):")
        print(r.get("raw_search_result_preview", "N/A")[:300])
        print(f"\nannexes (200 chars):")
        print((r.get("annexes") or "N/A")[:200])
        break

print("\n" + "="*60)

# Group E 조례 샘플: 부산시 지역상품
for r in d:
    if r["seed_id"] == "busan_local_product":
        print(f"=== {r['name']} ===")
        print(f"source_type: {r['source_type']}")
        print(f"raw_search_preview (300 chars):")
        print(r.get("raw_search_result_preview", "N/A")[:300])
        break
