import json, sys
sys.stdout.reconfigure(encoding="utf-8")

with open(r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_source_registry.json", encoding="utf-8") as f:
    reg = json.load(f)

print("=== 수집 결과 검증 ===")
print("총 %d건" % len(reg))
print()

total_articles = 0
total_text = 0
verified = 0
failed = 0
skipped = 0

for r in reg:
    st = r["status"]
    name = r["name"]
    arts = r.get("article_count", 0)
    annex = r.get("annex_count", 0)
    tlen = r.get("full_text_length", 0)
    total_articles += arts
    total_text += tlen
    official = (r.get("law_name_official") or "")[:30]
    eff = r.get("effective_date") or ""

    if st == "verified":
        mark = "V"
        verified += 1
    elif "skip" in st:
        mark = "S"
        skipped += 1
    else:
        mark = "X"
        failed += 1

    print("  [%s] %-40s | 조문:%3d 별표:%2d 텍스트:%7d자 | 시행:%s" % (mark, name, arts, annex, tlen, eff))

print()
print("총 조문수: %d건" % total_articles)
print("총 텍스트: %s자 (%dKB)" % (format(total_text, ","), total_text // 1024))
print("Verified: %d건" % verified)
print("Failed: %d건" % failed)
print("Skipped: %d건" % skipped)
