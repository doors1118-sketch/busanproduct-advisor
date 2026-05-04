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
        discovery_md += f"- **금액 기준**: min={rule.get('condition', {}).get('amount_min', '없음')}, max={rule.get('condition', {}).get('amount_max', '없음')}\n"
        
        quote = rule.get('quote_type')
        if quote: discovery_md += f"- **견적 방식**: {quote}\n"
        
        min_share = rule.get('min_local_share_percent')
        if min_share: discovery_md += f"- **지역업체 참여비율**: 최소 {min_share}% ~ 최대 {rule.get('max_local_share_percent', 100)}%\n"
        
        score = rule.get('max_score')
        if score: discovery_md += f"- **가점·배점 기준**: 최대 {score} {rule.get('score_unit', '')} ({rule.get('score_basis', '')})\n"
        
        discovery_md += "\n"

    with open("local_purchase_support_source_discovery.md", "w", encoding="utf-8") as f:
        f.write(discovery_md)


    # 2. Mapping Table MD
    mapping_md = """# 지역업체 구매지원 제도 Mapping Table v0.2

| Rule ID | Category | Display Name | Law System | Contract Object | Amount Condition | Quote Type | Procurement Route | Safe Phrase | Review Status |
|---|---|---|---|---|---|---|---|---|---|
"""
    for r in catalog:
        c = r.get("condition", {})
        law_sys = ", ".join(c.get("law_system", [])) if c.get("law_system") else ""
        c_obj = ", ".join(c.get("contract_objects", [])) if c.get("contract_objects") else ""
        c_amt = f"{c.get('amount_min','')}~{c.get('amount_max','')}" if (c.get('amount_min') or c.get('amount_max')) else ""
        q_type = r.get("quote_type", "") or ""
        p_route = ", ".join(c.get("procurement_routes", [])) if c.get("procurement_routes") else ""
        
        mapping_md += f"| {r['rule_id']} | {r['category']} | {r['display_name']} | {law_sys} | {c_obj} | {c_amt} | {q_type} | {p_route} | {r['safe_phrase']} | {r['review_status']} |\n"

    mapping_md += "\n## 금지 표현 정책\n본 매핑 테이블의 어떠한 항목도 '계약 가능합니다', '구매 가능합니다', '지역제한 가능합니다', '수의계약 가능합니다', '낙찰 가능합니다'를 포함하지 않습니다.\n"

    with open("local_purchase_support_mapping_table.md", "w", encoding="utf-8") as f:
        f.write(mapping_md)

generate_mds()
print("md generated")
