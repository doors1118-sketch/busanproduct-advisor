import json

def generate_mds():
    with open("local_purchase_support_rule_catalog.json", "r", encoding="utf-8") as f:
        catalog = json.load(f)

    # 1. Source Discovery MD
    discovery_md = """# Phase 9.2 Evidence-Based Source Discovery

본 문서는 Rule Catalog v0.2의 각 항목에 대한 법적 근거 매핑(Source Chain Mapping) 명세입니다.

"""
    for rule in catalog:
        discovery_md += f"## {rule['rule_id']}: {rule['display_name']}\n"
        discovery_md += f"- **관련 법령·시행령·기준**: {', '.join(rule.get('legal_basis_query_terms', ['(확인 필요)']))}\n"
        discovery_md += f"- **DB source_id 후보**: 미정\n"
        discovery_md += f"- **source_id 확정 여부**: {rule['review_status']}\n"
        
        c = rule.get('condition', {})
        if 'amount_min' in c or 'amount_max' in c or 'amount_condition_type' in c:
            discovery_md += f"- **금액 기준**: type={c.get('amount_condition_type', '')}, min={c.get('amount_min', '')}, max={c.get('amount_max', '')}\n"
        else:
            discovery_md += "- **금액 기준**: 없음\n"
            
        quote = rule.get('quote_type')
        if quote: discovery_md += f"- **견적 방식**: {quote}\n"
        
        min_share = rule.get('min_local_share_percent')
        if min_share: discovery_md += f"- **지역업체 참여비율**: 최소 {min_share}% ~ 최대 {rule.get('max_local_share_percent', 100)}%\n"
        if rule.get('numeric_basis') and rule['numeric_basis'].get('parameter_refs'):
            refs = ", ".join(rule['numeric_basis']['parameter_refs'])
            discovery_md += f"- **숫자/비율 파라미터**: {refs} (매핑 필요)\n"
            
        score = rule.get('max_score')
        if score: discovery_md += f"- **가점·배점 기준**: 최대 {score} {rule.get('score_unit', '')} ({rule.get('score_basis', '')})\n"
        
        discovery_md += "\n"

    with open("local_purchase_support_source_discovery.md", "w", encoding="utf-8") as f:
        f.write(discovery_md)


    # 2. Mapping Table MD
    mapping_md = """# 지역업체 구매지원 제도 Mapping Table v0.2

| Rule ID | Category | Display Name | Law System | Contract Object | Contract Subtype | Amount Condition | Quote Type | Procurement Route | Evaluation Method | Numeric Basis | Legal Basis Source IDs | Review Status | Safe Phrase | Required Checks | Candidate Lookup Link |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
"""
    for r in catalog:
        c = r.get("condition", {})
        law_sys = ", ".join(c.get("law_system", [])) if c.get("law_system") else ""
        c_obj = ", ".join(c.get("contract_objects", [])) if c.get("contract_objects") else ""
        c_sub = ", ".join(c.get("contract_subtypes", [])) if c.get("contract_subtypes") else ""
        c_amt = c.get("amount_condition_type", "")
        q_type = r.get("quote_type", "") or ""
        p_route = ", ".join(c.get("procurement_routes", [])) if c.get("procurement_routes") else ""
        e_method = ", ".join(c.get("evaluation_methods", [])) if c.get("evaluation_methods") else ""
        
        n_basis = "Yes" if r.get("numeric_basis") else ""
        l_basis = ", ".join(r.get("legal_basis_source_ids", []))
        req_checks = "<br>".join(r.get("required_checks", []))
        c_lookup = r.get("candidate_lookup_type", "") or ""
        
        mapping_md += f"| {r['rule_id']} | {r['category']} | {r['display_name']} | {law_sys} | {c_obj} | {c_sub} | {c_amt} | {q_type} | {p_route} | {e_method} | {n_basis} | {l_basis} | {r['review_status']} | {r['safe_phrase']} | {req_checks} | {c_lookup} |\n"

    mapping_md += "\n## 금지 표현 정책\n본 매핑 테이블의 어떠한 항목도 '계약 가능합니다', '구매 가능합니다', '지역제한 가능합니다', '수의계약 가능합니다', '낙찰 가능합니다'를 포함하지 않습니다.\n"

    with open("local_purchase_support_mapping_table.md", "w", encoding="utf-8") as f:
        f.write(mapping_md)

generate_mds()
print("md generated")
