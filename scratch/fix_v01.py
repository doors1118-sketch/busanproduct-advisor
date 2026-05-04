import json, sys, os
sys.stdout.reconfigure(encoding='utf-8')
base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'

# Load Candidate Data
candidate_file = os.path.join(base, 'legal_source_registry_master_by_jurisdiction_v0_1_candidate.json')
data = json.load(open(candidate_file, encoding='utf-8'))

# 1. Fix Busan Ordinances
# 2. Fix mas_2step
for c in data:
    sid = c.get('seed_id')
    norm = c.get('normalized_title', '')
    
    if sid in ['busan_local_product', 'busan_local_company']:
        c['jurisdiction_scope'] = ['local_contract', 'local_policy']
        c['buyer_type_scope'] = ['local_government', 'local_public_company', 'local_public_corporation', 'local_invested_institution', 'local_affiliated_institution']
        c['overlay_scope'] = ['local_product_preference', 'regional_preference']
        
    if '낙동강' in norm and '2단계경쟁' in norm:
        c['review_status'] = 'candidate_needs_review'
        c['registry_trust_level'] = 'conditional_verified'

# Re-save Candidate
with open(candidate_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

# 3. Fix Relations Graph
relations = [
    # 국가계약
    {"source": "국가를 당사자로 하는 계약에 관한 법률", "target": "국가를 당사자로 하는 계약에 관한 법률 시행령", "relation_type": "enforcement_decree"},
    {"source": "국가를 당사자로 하는 계약에 관한 법률 시행령", "target": "국가를 당사자로 하는 계약에 관한 법률 시행규칙", "relation_type": "enforcement_rule"},
    {"source": "국가를 당사자로 하는 계약에 관한 법률 시행규칙", "target": "정부 입찰ㆍ계약 집행기준", "relation_type": "administrative_rule"},
    {"source": "정부 입찰ㆍ계약 집행기준", "target": "계약예규 계열", "relation_type": "administrative_rule"},
    # 지방계약
    {"source": "지방자치단체를 당사자로 하는 계약에 관한 법률", "target": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령", "relation_type": "enforcement_decree"},
    {"source": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령", "target": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행규칙", "relation_type": "enforcement_rule"},
    {"source": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행규칙", "target": "지방자치단체 입찰 및 계약집행기준", "relation_type": "administrative_rule"},
    {"source": "지방자치단체 입찰 및 계약집행기준", "target": "지방자치단체 입찰시 낙찰자 결정기준", "relation_type": "administrative_rule"},
    # 조달사업
    {"source": "조달사업에 관한 법률", "target": "조달사업에 관한 법률 시행령", "relation_type": "enforcement_decree"},
    {"source": "조달사업에 관한 법률 시행령", "target": "조달사업에 관한 법률 시행규칙", "relation_type": "enforcement_rule"},
    {"source": "조달사업에 관한 법률 시행규칙", "target": "국가종합전자조달시스템 종합쇼핑몰 운영규정", "relation_type": "procurement_guideline"},
    {"source": "조달사업에 관한 법률 시행규칙", "target": "물품 다수공급자계약 업무처리규정", "relation_type": "procurement_guideline"},
    {"source": "조달사업에 관한 법률 시행규칙", "target": "MAS 2단계경쟁 관련 기준 후보", "relation_type": "candidate_relation"},
    {"source": "조달사업에 관한 법률 시행규칙", "target": "혁신제품 구매 운영 규정", "relation_type": "procurement_guideline"},
    {"source": "조달사업에 관한 법률 시행규칙", "target": "우수조달물품 지정·관리 규정", "relation_type": "procurement_guideline"},
    # 공공기관
    {"source": "공공기관의 운영에 관한 법률", "target": "공공기관의 운영에 관한 법률 시행령", "relation_type": "enforcement_decree"},
    {"source": "공공기관의 운영에 관한 법률 시행령", "target": "공기업ㆍ준정부기관 계약사무규칙", "relation_type": "administrative_rule"},
    {"source": "공공기관의 운영에 관한 법률 시행령", "target": "공기업ㆍ준정부기관 회계사무규칙", "relation_type": "administrative_rule"},
    {"source": "public_institution_contract", "target": "national_contract", "relation_type": "fallback_reference_to_national_contract", "application_condition": "계약사무규칙에 규정되지 아니한 사항"},
    {"source": "공기업ㆍ준정부기관 계약사무규칙", "target": "기타공공기관 계약사무 운영규정 후보", "relation_type": "candidate_relation"},
    # 중소기업 정책 체계
    {"source": "중소기업제품 구매촉진 및 판로지원에 관한 법률", "target": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령", "relation_type": "enforcement_decree"},
    {"source": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령", "target": "중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역", "relation_type": "cross_cutting_policy"},
    {"source": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령", "target": "조달청 제조물품 직접생산확인 기준", "relation_type": "cross_cutting_policy"},
    {"source": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령", "target": "중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙", "relation_type": "cross_cutting_policy"},
    # 정책기업
    {"source": "여성기업지원에 관한 법률", "target": "여성기업지원에 관한 법률 시행령", "relation_type": "enforcement_decree"},
    {"source": "장애인기업활동 촉진법", "target": "장애인기업활동 촉진법 시행령", "relation_type": "enforcement_decree"},
    {"source": "사회적기업 육성법", "target": "사회적기업 육성법 시행령", "relation_type": "enforcement_decree"}
]

relations_file = os.path.join(base, 'legal_relation_seed_by_jurisdiction_v0_1.json')
with open(relations_file, 'w', encoding='utf-8') as f:
    json.dump(relations, f, ensure_ascii=False, indent=2)

# 4. Recompute Readiness Report
trust_level_counts = {}
j_scope_counts = {}
b_scope_counts = {}
o_scope_counts = {}

for c in data:
    tl = c.get('registry_trust_level')
    trust_level_counts[tl] = trust_level_counts.get(tl, 0) + 1
    for j in c.get('jurisdiction_scope', []): j_scope_counts[j] = j_scope_counts.get(j, 0) + 1
    for b in c.get('buyer_type_scope', []): b_scope_counts[b] = b_scope_counts.get(b, 0) + 1
    for o in c.get('overlay_scope', []): o_scope_counts[o] = o_scope_counts.get(o, 0) + 1

# Check conditions
freeze_pass = True
blocking_issues = []

# wrong_match in verified?
for c in data:
    if c['registry_trust_level'] == 'wrong_match' and c['review_status'] == 'verified':
        freeze_pass = False; blocking_issues.append(f"Wrong match {c['normalized_title']} is verified.")

# busan in national_contract?
busan = [c for c in data if c.get('seed_id') in ['busan_local_product', 'busan_local_company']]
for b in busan:
    if 'national_contract' in b.get('jurisdiction_scope', []):
        freeze_pass = False; blocking_issues.append("Busan ordinance classified as national_contract.")

# Relations count check
if len(relations) < 5:
    freeze_pass = False; blocking_issues.append("Relation graph has less than 5 connections.")

readiness = {
    "v0_1_freeze_ready": freeze_pass,
    "pass_conditions_met": freeze_pass,
    "blocking_issues": blocking_issues,
    "total_sources": len(data),
    "trust_level_distribution": trust_level_counts,
    "jurisdiction_distribution": j_scope_counts,
    "buyer_type_distribution": b_scope_counts,
    "overlay_distribution": o_scope_counts,
    "relation_types_count": len(relations)
}

readiness_file = os.path.join(base, 'legal_registry_freeze_readiness_report.json')
with open(readiness_file, 'w', encoding='utf-8') as f:
    json.dump(readiness, f, ensure_ascii=False, indent=2)

print(f"Fix completed. Readiness: {freeze_pass}. Relations count: {len(relations)}")
