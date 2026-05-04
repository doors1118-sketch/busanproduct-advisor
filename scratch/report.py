import json, sys
sys.stdout.reconfigure(encoding="utf-8")
base = r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data"

log = json.load(open(base + r"\legal_chart_collection_log.json", encoding="utf-8"))
print("=== Collection Log ===")
for k,v in log.items():
    print("  %s: %s" % (k, v))

print()
print("=== Failed list ===")
failed = json.load(open(base + r"\legal_chart_failed_or_partial_list.json", encoding="utf-8"))
for f in failed:
    nn = f.get("node_name", "?")
    cs = f.get("collection_status", "?")
    err = f.get("error", "")
    print("  - %s | %s | %s" % (nn, cs, err))

print()
print("=== Already collected (from existing registry) ===")
already = json.load(open(base + r"\legal_source_already_collected_map.json", encoding="utf-8"))
for a in already:
    print("  - %s -> %s" % (a["node_name"], a.get("matched_seed_id", "")))

print()
reg_patch = json.load(open(base + r"\legal_source_registry_patch_from_charts.json", encoding="utf-8"))
total_arts = sum(r.get("article_count", 0) for r in reg_patch)
total_text = sum(r.get("full_text_length", 0) for r in reg_patch)
print("Registry patch: %d sources, %d articles, %s chars" % (len(reg_patch), total_arts, format(total_text, ",")))

cand_patch = json.load(open(base + r"\legal_source_candidate_patch_from_charts.json", encoding="utf-8"))
print("Candidate patch: %d sources" % len(cand_patch))
