import json, sys
sys.stdout.reconfigure(encoding='utf-8')
base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

reg = json.load(open(base + r'\legal_source_registry.json', encoding='utf-8'))
for r in reg:
    print("%s | %s | %s" % (r.get('seed_id', ''), r.get('name', ''), r.get('normalized_title', '')))
