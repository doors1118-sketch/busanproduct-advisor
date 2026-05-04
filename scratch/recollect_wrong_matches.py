import requests, sys, json, time, re, hashlib, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

sys.stdout.reconfigure(encoding='utf-8')
KST = timezone(timedelta(hours=9))
OC = 'busanproduct1'
BASE = 'http://www.law.go.kr/DRF'

targets = [
    ('pps_mas_standard', '다수공급자계약 업무처리규정'),
    ('mas_2step', '다수공급자계약 2단계경쟁 업무처리기준'),
    ('innovation_prototype', '혁신제품 구매 운영 규정'),
    ('excellent_procurement', '우수조달물품 지정 관리 규정'),
]

def api_get(ep, params):
    params['OC'] = OC
    params['type'] = 'XML'
    r = requests.get(BASE + '/' + ep, params=params, timeout=15)
    if r.status_code != 200: return None
    return ET.fromstring(r.content) if len(r.content) > 50 else None

def normalize_title(raw):
    s = re.sub(r'\[.*?\]', '', raw).strip()
    s = re.sub(r'^\([가-힣]+\)\s*', '', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s.replace('·', 'ㆍ')

def classify(name):
    if re.search(r'시행규칙|부령', name): return 'enforcement_rule'
    if re.search(r'시행령|대통령령', name): return 'enforcement_decree'
    if '사무규칙' in name or '회계사무' in name: return 'enforcement_rule'
    if re.search(r'법률|에\s*관한\s*법$|촉진법$|육성법$|지원법$', name): return 'act'
    if '훈령' in name: return 'instruction'
    if re.search(r'예규|집행기준|결정기준', name): return 'regulation'
    if re.search(r'고시|지침|규정|기준|요령|세칙|내역', name): return 'notice'
    if re.search(r'조례|자치법규', name): return 'ordinance'
    return 'admin_rule'

def make_url(name, stype):
    clean = re.sub(r'\[.*?\]', '', name).strip()
    encoded = urllib.parse.quote(clean)
    if stype in ('law','act','enforcement_decree','enforcement_rule'):
        return 'https://www.law.go.kr/법령/' + encoded
    return 'https://www.law.go.kr/행정규칙/' + encoded

def make_hash(norm_title, eff_date, mst, text_len):
    s = '%s|%s|%s|%s' % (norm_title, eff_date or '', mst or '', text_len or 0)
    return hashlib.sha256(s.encode()).hexdigest()[:16]

collected = {}

for seed_id, query in targets:
    print(f"Searching: {query}")
    root = api_get('lawSearch.do', {'target': 'admrul', 'query': query, 'display': '1'})
    if root is None:
        print("  failed to search")
        continue
    items = root.findall('.//admrul')
    if not items:
        print("  no results")
        continue
    
    top = items[0]
    serial = top.findtext('행정규칙일련번호') or ''
    name = top.findtext('행정규칙명') or ''
    eff_date = top.findtext('발령일자') or ''
    org = top.findtext('소관부처명') or ''
    print(f"  found: {name} ({serial})")
    
    # get full text
    full = api_get('lawService.do', {'target': 'admrul', 'ID': serial})
    art_count = 0
    text_len = 0
    if full is not None:
        for child in full:
            if child.tag == '조문내용' and child.text:
                art_count += 1
                text_len += len(child.text)
    
    print(f"  arts={art_count}, text={text_len}")
    
    norm = normalize_title(name)
    cat = classify(name)
    url = make_url(name, 'admrul')
    vh = make_hash(norm, eff_date, serial, text_len)
    
    collected[seed_id] = {
        'seed_id': seed_id,
        'name': query,
        'law_name_official': name,
        'normalized_title': norm,
        'source_type': 'admrul_notice',
        'law_category': cat,
        'article_count': art_count,
        'full_text_length': text_len,
        'effective_date': eff_date,
        'issuing_org': org,
        'mst': serial,
        'official_url': url,
        'version_hash': vh,
        'status': 'verified',
        'review_status': 'verified',
        'collected_at': datetime.now(KST).isoformat()
    }
    time.sleep(1)

# Now update master registry
base_path = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_source_registry_master_by_jurisdiction.json'
master = json.load(open(base_path, encoding='utf-8'))

updated = 0
for m in master:
    sid = m.get('seed_id')
    if sid in collected:
        new_data = collected[sid]
        for k, v in new_data.items():
            m[k] = v
        updated += 1

with open(base_path, 'w', encoding='utf-8') as f:
    json.dump(master, f, ensure_ascii=False, indent=2)

print(f"\nUpdated {updated} items in master registry.")
