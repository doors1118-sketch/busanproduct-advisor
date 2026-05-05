import json
d = json.load(open(r"purchase_support_rule_source_map.merged.v2.json", "r", encoding="utf-8"))
for k, v in d.items():
    if v["source_chain_status"] == "pending_resolution":
        print(f"{k}: primary={len(v['primary_source_ids'])}, related={len(v['related_source_ids'])}")
        print(f"  unmatched: {v['unmatched_query_terms']}")
