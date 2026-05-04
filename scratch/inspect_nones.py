import json
base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
manifest = json.load(open(base + r'\legal_update_manifest_v0_1_1.json', encoding='utf-8'))
nones = [m for m in manifest if m['law_api_target'] == 'none']
for n in nones:
    print(f"{n['source_id'][:12]}  {n['source_type']:15s}  {n.get('update_priority','?'):10s}  {n.get('update_enabled','')}  {n['normalized_title'][:50]}")
print(f"Total none: {len(nones)}")
pdfs = [m for m in manifest if m['source_type'] == 'pdf_manual']
print(f"\nPDF manuals: {len(pdfs)}")
for p in pdfs:
    print(f"  {p['source_id'][:12]}  active_rule={p['active_for_rule']}  priority={p['update_priority']}  {p['normalized_title'][:60]}")
# Check skip_api
skips = [m for m in manifest if m['source_type'] == 'skip_api']
print(f"\nskip_api: {len(skips)}")
for s in skips:
    print(f"  {s['source_id'][:12]}  active_rule={s['active_for_rule']}  {s['normalized_title'][:60]}")
