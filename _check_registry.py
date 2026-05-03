import json
d = json.load(open(r'app\data\legal_source_registry.json', 'r', encoding='utf-8'))
print(f"총 {len(d)}건")
for r in d:
    g = r["group"]
    n = r["name"]
    s = r["status"]
    sc = len(r["steps_completed"])
    sf = len(r["steps_failed"])
    mst = r.get("mst", "N/A")
    eff = r.get("effective_date", "N/A")
    print(f"  [{g}] {n}: {s} (ok={sc} fail={sf}) mst={mst} eff={eff}")

c = json.load(open(r'app\data\legal_source_candidate.json', 'r', encoding='utf-8'))
print(f"\nCandidates: {len(c)}건")
