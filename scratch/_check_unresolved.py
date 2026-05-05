import json
d = json.load(open("purchase_support_rule_source_map.json", "r", encoding="utf-8"))
for k, v in d.items():
    for p in v.get("numeric_parameters", []):
        if p.get("resolved_value") is None and p.get("requires_manual_numeric_verification"):
            ref = p.get("parameter_ref", "")
            hint = p.get("expected_value_hint", "")
            src = p.get("source_law_ref", "")
            print(f"{k} | {ref} | hint={hint} | source={src}")
