"""확인: company_api_mapping_required 규칙 상세"""
import json
d = json.load(open("purchase_support_rule_source_map.json", "r", encoding="utf-8"))
for k, v in d.items():
    if v["source_chain_status"] == "company_api_mapping_required":
        print(f"\n{'='*50}")
        print(f"rule_id: {k}")
        print(f"display_name: {v.get('display_name','')}")
        print(f"category: {v.get('category','')}")
        print(f"primary_source_ids: {v.get('primary_source_ids',[])}")
        print(f"related_source_ids: {v.get('related_source_ids',[])}")
        print(f"remaining_gap_reason: {v.get('remaining_gap_reason','')}")
