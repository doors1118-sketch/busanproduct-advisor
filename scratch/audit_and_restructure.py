import json, sys, os, re
sys.stdout.reconfigure(encoding='utf-8')
base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

# 1. Load Data
try:
    reg = json.load(open(os.path.join(base, 'legal_source_registry.json'), encoding='utf-8'))
    patch = json.load(open(os.path.join(base, 'legal_source_registry_patch_from_charts.json'), encoding='utf-8'))
except Exception as e:
    print(f"Error loading files: {e}")
    sys.exit(1)

audit_results = []
master_registry = []
relations = []

# Exact Match Audit definitions
wrong_match_keywords = ['낙동강', '반송', '관세청', '수출', '우수조달공동상표', '추가특수조건']

for r in reg:
    seed_id = r.get('seed_id', '')
    name = r.get('name', '')
    norm_title = r.get('normalized_title', '')
    
    match_status = 'exact_match'
    
    if r.get('article_count', 0) == 0:
        match_status = 'needs_manual_source'
    elif any(kw in norm_title for kw in wrong_match_keywords):
        match_status = 'wrong_match'
    elif '고시' in norm_title and '규정' in name:
        match_status = 'acceptable_broader_match'
    elif '지침' in norm_title and '기준' in name:
        match_status = 'acceptable_broader_match'
    
    if seed_id == 'innovation_product': match_status = 'acceptable_broader_match'
    if seed_id in ['contract_regulation', 'pps_mas_standard', 'mas_2step', 'excellent_procurement', 'innovation_prototype'] and r.get('article_count',0) > 0:
        if any(kw in norm_title for kw in wrong_match_keywords):
            match_status = 'wrong_match'

    # Jurisdictions and Overlays
    jurisdiction = 'national_contract'
    if '지방' in norm_title or '지방' in name:
        jurisdiction = 'local_contract'
    if '공기업' in norm_title or '공공기관' in norm_title:
        jurisdiction = 'public_institution_contract'
    if '지방공기업' in norm_title:
        jurisdiction = 'local_public_institution_contract'
        
    buyer_type = 'all'
    if jurisdiction == 'local_contract': buyer_type = 'local_government'
    elif jurisdiction == 'national_contract': buyer_type = 'national_government'
    elif jurisdiction == 'public_institution_contract': buyer_type = 'public_institution'
    
    overlay = []
    if '중소기업' in norm_title or '구매촉진' in norm_title: overlay.append('sme_purchase')
    if '경쟁제품' in norm_title: overlay.append('sme_competition_product')
    if '여성' in norm_title or '장애인' in norm_title or '사회적' in norm_title: overlay.append('policy_company')
    if '혁신' in norm_title: overlay.append('innovation_product')
    if '우수' in norm_title: overlay.append('excellent_procurement')
    if '기술개발' in norm_title: overlay.append('technology_development_product')
    if '직접생산' in norm_title: overlay.append('direct_production')
    if '다수공급자' in norm_title or '쇼핑몰' in norm_title: overlay.append('mas_shopping_mall')
    if '부산' in norm_title or '지역상품' in norm_title: overlay.append('local_product_preference')
    
    r['jurisdiction_scope'] = jurisdiction
    r['buyer_type_scope'] = buyer_type
    r['overlay_scope'] = overlay
    r['relation_type'] = 'primary' if r.get('source_type') in ['act', 'enforcement_decree', 'enforcement_rule'] else 'subordinate'
    r['applicability_scope'] = 'general' if not overlay else 'conditional'
    r['required_slots'] = ['contract_method']
    r['review_status'] = 'verified' if match_status in ['exact_match', 'acceptable_broader_match'] else 'needs_review'
    
    audit_results.append({
        'seed_id': seed_id,
        'seed_name': name,
        'normalized_title': norm_title,
        'match_status': match_status
    })
    
    master_registry.append(r)

# Relations
relations.append({
    'source': 'public_institution_contract',
    'target': 'national_contract',
    'relation_type': 'fallback_reference_to_national_contract',
    'application_condition': '계약사무규칙에 규정되지 아니한 사항'
})

# Deduplicate Patch
dedup_report = []
candidate_queue = []
master_names = {r['normalized_title'] for r in master_registry}

for p in patch:
    norm_title = p.get('normalized_title', '')
    name = p.get('node_name', '')
    
    status = 'new_verified_source'
    if norm_title in master_names:
        status = 'already_in_master'
    elif '조례' in norm_title or '지침' in norm_title:
        status = 'candidate_needs_review'
        candidate_queue.append(p)
    elif '▼' in name or '고시금액' in name:
        status = 'out_of_scope'
        
    p['dedup_status'] = status
    dedup_report.append({
        'node_name': name,
        'normalized_title': norm_title,
        'dedup_status': status
    })


# Save files
def save_json(filename, data):
    with open(os.path.join(base, filename), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

save_json('legal_seed_exact_match_audit.json', audit_results)
save_json('legal_source_registry_master_by_jurisdiction.json', master_registry)
save_json('legal_relation_seed_by_jurisdiction.json', relations)
save_json('legal_buyer_type_scope_map.json', {'local_government': 'local_contract', 'national_government': 'national_contract', 'public_institution': 'public_institution_contract'})
save_json('legal_overlay_scope_map.json', {'sme_purchase': '중소기업', 'policy_company': '정책기업', 'innovation_product': '혁신제품'})
save_json('legal_patch_dedup_report.json', dedup_report)
save_json('legal_candidate_review_queue.json', candidate_queue)
save_json('legal_registry_restore_report.json', {'restored': len(master_registry), 'candidates': len(candidate_queue)})

print("Generated 8 JSON files successfully.")
