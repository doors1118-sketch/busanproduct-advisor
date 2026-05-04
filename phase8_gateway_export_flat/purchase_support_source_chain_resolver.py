import json
import os
import sys
from collections import defaultdict

# Add current dir to sys.path to import app module
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.gateway.db.reader import ReadOnlyDatabase

QUERY_EXPANSION = {
    "소액수의계약": ["소액수의", "수의계약", "견적서", "1인 견적", "2인 이상 견적", "시행령 제25조", "시행령 제26조"],
    "지역제한": ["지역제한", "주된 영업소", "입찰참가자격 제한", "제한경쟁", "시행령 제20조", "시행령 제21조"],
    "제한경쟁": ["제한경쟁", "주된 영업소", "입찰참가자격 제한"],
    "수의계약": ["수의계약", "소액수의", "견적서"],
    "1인 견적": ["1인 견적", "수의계약"],
    "2인 이상 견적": ["2인 이상", "안내공고", "수의계약", "견적서"],
    "MAS 2단계경쟁": ["2단계경쟁", "다수공급자계약"],
    "2단계경쟁": ["2단계경쟁", "다수공급자계약"],
    "지역업체 참여도": ["참여도", "지역업체 가점", "지역업체", "가산점"],
    "지역의무공동도급": ["지역의무공동도급", "공동수급", "공동계약"],
    "종합평가방식": ["종합평가방식", "다수공급자계약"],
    "제3자단가계약": ["제3자를 위한 단가계약", "제3자단가", "제3자 단가", "납품요구", "조달사업법 시행령 제12조"],
    "직접 납품요구": ["직접 납품요구", "납품요구", "제3자를 위한 단가계약"],
    "중증장애인생산품": ["중증장애인생산품", "장애인생산품", "우선구매", "사회적경제기업", "사회적가치"]
}

MANUAL_SEED_TERMS = {
    "R_DIRECT_GENERAL_SMALL_AMOUNT": ["지방계약법 시행령 제25조", "국가계약법 시행령 제26조", "소액수의계약"],
    "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY": ["지방계약법 시행령 제25조", "국가계약법 시행령 제26조", "소액수의계약"],
    "R_REGIONAL_RESTRICTION_GOODS": ["지방계약법 시행령", "국가계약법 시행령", "입찰참가자격 제한", "제한경쟁", "주된 영업소", "물품"],
    "R_REGIONAL_RESTRICTION_SERVICE": ["지방계약법 시행령", "국가계약법 시행령", "입찰참가자격 제한", "제한경쟁", "주된 영업소", "용역"],
    "R_REGIONAL_RESTRICTION_CONSTRUCTION": ["지방계약법 시행령", "국가계약법 시행령", "입찰참가자격 제한", "제한경쟁", "주된 영업소", "공사"],
    "R_LIMITED_COMPETITION_REVIEW": ["지방계약법 시행령", "국가계약법 시행령", "입찰참가자격 제한", "제한경쟁"],
    "R_THIRD_PARTY_UNIT_PRICE_DIRECT_ORDER_REVIEW": ["조달사업법 시행령", "제3자를 위한 단가계약", "제3자단가계약", "납품요구"],
    "R_SOCIAL_VALUE_PURCHASE_REVIEW": ["중증장애인생산품", "장애인생산품", "우선구매", "사회적경제기업", "사회적가치"]
}

CATALOG_PATH = "local_purchase_support_rule_catalog.json"
DB_PATH = "app/data/legal_db_v0_1_3.sqlite"
MAP_OUTPUT_PATH = "purchase_support_rule_source_map.json"
REPORT_OUTPUT_PATH = "purchase_support_source_chain_discovery_report.md"

def calculate_rank_score(source, original_terms, expanded_terms, rule_category):
    score = 0
    breakdown = {}
    
    # 1. review_status
    if source["review_status"] == "verified":
        score += 50
        breakdown["review_status"] = 50
    elif source["review_status"] == "candidate_needs_review":
        score += 20
        breakdown["review_status"] = 20
    else:
        breakdown["review_status"] = 0
        
    # 2. source_type
    st = source["source_type"]
    if st in ("law", "law_decree", "law_rule"):
        score += 30
        breakdown["source_type"] = 30
    elif st and st.startswith("admrul"):
        score += 20
        breakdown["source_type"] = 20
    elif st in ("ordinance", "local_rule"):
        score += 15
        breakdown["source_type"] = 15
    elif st in ("pdf_manual", "guide", "manual"):
        score += 10
        breakdown["source_type"] = 10
    else:
        breakdown["source_type"] = 0
        
    # 3. query match
    match_score = 0
    title_name = ((source["normalized_title"] or "") + " " + (source["source_name"] or "")).replace(" ", "")
    scope_fields = "".join(filter(None, [
        source["applicability_scope"], source["activation_mode"], 
        source["contract_object_scope"], source["procurement_route_scope"], 
        source["law_category"], source["source_type"]
    ]))
    
    for t in original_terms:
        t_no_space = t.replace(" ", "")
        if t_no_space in title_name:
            match_score = max(match_score, 30)
        elif t_no_space in scope_fields:
            match_score = max(match_score, 8)
            
    if match_score < 30:
        for t in expanded_terms:
            t_no_space = t.replace(" ", "")
            if t_no_space in title_name:
                match_score = max(match_score, 15)
            elif t_no_space in scope_fields:
                match_score = max(match_score, 8)
            
    score += match_score
    breakdown["query_match"] = match_score
    
    # 4. category_fit
    cat_score = 0
    # Simple heuristics mapping category to expected keywords in titles
    expected = {
        "shopping_mall": ["다수공급자계약", "제3자단가", "카탈로그", "우수조달물품"],
        "joint_contract": ["공동계약"],
        "regional_restriction": ["지방계약", "국가계약", "조달사업법"],
        "direct_contract": ["수의계약", "지방계약", "국가계약"],
        "evaluation": ["적격심사", "낙찰자 결정기준"],
        "participation_points": ["낙찰자 결정기준"],
        "local_priority": ["지역상품", "조례"]
    }
    
    if any(kw in title_name for kw in expected.get(rule_category, [])):
        cat_score = 20
    elif match_score > 0:
        cat_score = 10
    else:
        cat_score = -10
        
    score += cat_score
    breakdown["category_fit"] = cat_score
    
    # 5. over_specific
    spec_penalty = 0
    if "부산광역시" in title_name and rule_category not in ("local_priority", "joint_contract") and "부산" not in "".join(original_terms):
        spec_penalty = -10
    elif "조례" in title_name and rule_category != "local_priority" and "조례" not in "".join(original_terms):
        spec_penalty = -10
        
    score += spec_penalty
    breakdown["specificity_penalty"] = spec_penalty
    
    return score, breakdown

def resolve_sources():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    db = ReadOnlyDatabase(DB_PATH)
    
    # 6.1 Report Summary queries
    source_type_summary = db.execute("SELECT source_type, COUNT(*) as cnt FROM legal_source GROUP BY source_type ORDER BY cnt DESC")
    law_category_summary = db.execute("SELECT law_category, COUNT(*) as cnt FROM legal_source GROUP BY law_category ORDER BY cnt DESC")
    
    rule_source_map = {}
    
    summary = {
        "total_rules": len(catalog),
        "company_api": 0,
        "mapped_verified": 0,
        "mapped_candidate": 0,
        "partial_mapped": 0,
        "pending_resolution": 0,
    }

    for rule in catalog:
        rule_id = rule["rule_id"]
        review_status = rule.get("review_status")
        
        # Override with MANUAL_SEED_TERMS if exists
        query_terms = MANUAL_SEED_TERMS.get(rule_id, rule.get("legal_basis_query_terms", []))
        
        # 1. Primary Sources Matching
        primary_sources = []
        matched_original_terms = set()
        matched_expanded_terms = set()
        unmatched_terms = set(query_terms)
        
        all_search_terms = []
        term_map = {}
        for term in query_terms:
            expanded = QUERY_EXPANSION.get(term, [term])
            all_search_terms.extend(expanded)
            for e in expanded:
                term_map[e] = term
                
        # Deduplicate search terms
        all_search_terms = list(set(all_search_terms))
        
        for s_term in all_search_terms:
            query = """
            SELECT *
            FROM legal_source
            WHERE (
                normalized_title LIKE ? OR 
                source_name LIKE ? OR
                applicability_scope LIKE ? OR
                activation_mode LIKE ? OR
                contract_object_scope LIKE ? OR
                procurement_route_scope LIKE ? OR
                law_category LIKE ? OR
                source_type LIKE ?
            )
            AND review_status NOT IN ('wrong_match', 'needs_manual_source')
            """
            like_term = f"%{s_term}%"
            rows = db.execute(query, (like_term,)*8)
            
            if rows:
                original_term = term_map[s_term]
                if s_term == original_term:
                    matched_original_terms.add(s_term)
                else:
                    matched_expanded_terms.add(s_term)
                    
                if original_term in unmatched_terms:
                    unmatched_terms.remove(original_term)
                for r in rows:
                    primary_sources.append(r)
        
        # Deduplicate and calculate scores
        unique_primary = {}
        for ps in primary_sources:
            sid = ps["source_id"]
            if sid not in unique_primary:
                rank_score, breakdown = calculate_rank_score(ps, query_terms, [t for t in all_search_terms if t not in query_terms], rule["category"])
                unique_primary[sid] = {
                    "id": sid,
                    "title": ps["normalized_title"],
                    "status": ps["review_status"],
                    "source_type": ps["source_type"],
                    "law_category": ps["law_category"],
                    "rank_score": rank_score,
                    "score_breakdown": breakdown
                }
        
        # Sort by rank_score DESC
        primary_source_details = sorted(list(unique_primary.values()), key=lambda x: x["rank_score"], reverse=True)
        primary_source_ids = [ps["id"] for ps in primary_source_details]
        
        # 2. Related Sources Matching
        related_source_details = []
        if primary_source_ids:
            primary_titles = [ps["title"] for ps in primary_source_details]
            placeholders = ",".join(["?"] * len(primary_titles))
            
            rel_query = f"""
            SELECT DISTINCT s.*
            FROM legal_relation r
            JOIN legal_source s ON (s.normalized_title = r.source_title OR s.normalized_title = r.target_title)
            WHERE (r.source_title IN ({placeholders}) OR r.target_title IN ({placeholders}))
            AND s.source_id NOT IN ({",".join(["?"] * len(primary_source_ids))})
            AND s.review_status NOT IN ('wrong_match', 'needs_manual_source')
            AND r.review_status NOT IN ('wrong_match', 'needs_manual_source')
            """
            params = tuple(primary_titles + primary_titles + primary_source_ids)
            rel_rows = db.execute(rel_query, params)
            
            for rr in rel_rows:
                rank_score, breakdown = calculate_rank_score(rr, query_terms, [], rule["category"])
                related_source_details.append({
                    "id": rr["source_id"],
                    "title": rr["normalized_title"],
                    "status": rr["review_status"],
                    "source_type": rr["source_type"],
                    "law_category": rr["law_category"],
                    "rank_score": rank_score,
                    "score_breakdown": breakdown
                })
            
            # Sort related sources
            related_source_details = sorted(related_source_details, key=lambda x: x["rank_score"], reverse=True)
            
        # 3. Numeric Parameters
        numeric_parameters = []
        numeric_basis = rule.get("numeric_basis")
        has_unresolved_numeric = False
        
        if numeric_basis and numeric_basis.get("parameter_refs"):
            for ref in numeric_basis["parameter_refs"]:
                numeric_parameters.append({
                    "parameter_ref": ref,
                    "candidate_source_ids": primary_source_ids.copy(),
                    "expected_value_hint": numeric_basis.get("expected_value_hint"),
                    "resolved_value": None,
                    "requires_manual_numeric_verification": True,
                    "parameter_status": "candidate_only"
                })
            has_unresolved_numeric = True 
            
        # 4. Status Determination
        has_verified = any(ps["status"] == "verified" for ps in primary_source_details)
        top_rank_score = primary_source_details[0]["rank_score"] if primary_source_details else 0
        
        if review_status == "company_api_mapping_required":
            status = "company_api_mapping_required"
            summary["company_api"] += 1
        else:
            if len(unmatched_terms) == len(query_terms) and len(query_terms) > 0:
                status = "pending_resolution"
                summary["pending_resolution"] += 1
            elif len(unmatched_terms) > 0 or has_unresolved_numeric:
                status = "partial_mapped"
                summary["partial_mapped"] += 1
            else:
                if has_verified and len(unmatched_terms) == 0 and not has_unresolved_numeric:
                    status = "mapped_verified"
                    summary["mapped_verified"] += 1
                else:
                    status = "mapped_candidate"
                    summary["mapped_candidate"] += 1
                    
        # Gap Reason
        gap_reason = "None"
        if status == "pending_resolution":
            gap_reason = "No matching sources found for any query terms"
        elif status == "partial_mapped":
            if has_unresolved_numeric:
                gap_reason = "Numeric parameters pending manual verification"
            else:
                gap_reason = f"Unmatched required terms: {', '.join(unmatched_terms)}"
        elif status == "mapped_candidate":
            gap_reason = "Verified source missing"
            
        # High priority count
        high_priority_count = sum(1 for ps in primary_source_details if ps["rank_score"] >= 80 or (ps["rank_score"] >= 70 and ps["score_breakdown"].get("query_match", 0) > 0))
        
        rule_source_map[rule_id] = {
            "rule_id": rule_id,
            "display_name": rule["display_name"],
            "category": rule["category"],
            "primary_source_ids": primary_source_ids,
            "related_source_ids": [rs["id"] for rs in related_source_details],
            "matched_query_terms": {
                "original": list(matched_original_terms),
                "expanded": list(matched_expanded_terms)
            },
            "unmatched_query_terms": list(unmatched_terms),
            "numeric_parameters": numeric_parameters,
            "source_chain_status": status,
            "primary_source_details": primary_source_details,
            "related_source_details": related_source_details,
            "high_priority_source_count": high_priority_count,
            "remaining_gap_reason": gap_reason
        }

    # Write Map JSON
    with open(MAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rule_source_map, f, ensure_ascii=False, indent=2)
        
    # Write Report MD
    with open(REPORT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 9.2-C Source Chain Discovery Report\n\n")
        
        f.write("## 1. Database Distributions\n")
        f.write("### Source Types\n")
        for row in source_type_summary:
            f.write(f"- `{row['source_type']}`: {row['cnt']}\n")
            
        f.write("\n### Law Categories\n")
        for row in law_category_summary:
            f.write(f"- `{row['law_category']}`: {row['cnt']}\n")
            
        f.write("\n## 2. Mapping Summary\n")
        f.write(f"- **Total Rules**: {summary['total_rules']}\n")
        f.write(f"- **Mapped Verified**: {summary['mapped_verified']}\n")
        f.write(f"- **Mapped Candidate**: {summary['mapped_candidate']}\n")
        f.write(f"- **Partial Mapped**: {summary['partial_mapped']}\n")
        f.write(f"- **Pending Resolution**: {summary['pending_resolution']}\n")
        f.write(f"- **Company API / Outside DB**: {summary['company_api']}\n\n")
        
        f.write("## 3. Rule Source Mapping Details\n\n")
        
        categories = defaultdict(list)
        for r in rule_source_map.values():
            categories[r["category"]].append(r)
            
        for cat, rules in categories.items():
            f.write(f"### Category: `{cat}`\n\n")
            f.write("| Rule ID | Name | Status | Matched Terms | Unmatched Terms | Numeric Pending | Candidate Sources | Top Candidate by Score |\n")
            f.write("|---------|------|--------|---------------|-----------------|-----------------|-------------------|------------------------|\n")
            for r in rules:
                total_cnt = len(r["primary_source_ids"])
                
                matched = ", ".join(r["matched_query_terms"]["original"] + r["matched_query_terms"]["expanded"]) if (r["matched_query_terms"]["original"] or r["matched_query_terms"]["expanded"]) else "None"
                unmatched = ", ".join(r["unmatched_query_terms"]) if r["unmatched_query_terms"] else "None"
                numeric_pending = "Yes" if r["numeric_parameters"] else "No"
                
                top_source = r["primary_source_details"][0] if r["primary_source_details"] else None
                top_html = f"{top_source['title']} (Score: {top_source['rank_score']})" if top_source else "None"
                
                f.write(f"| `{r['rule_id']}` | {r['display_name']} | `{r['source_chain_status']}` | {matched} | {unmatched} | {numeric_pending} | {total_cnt} | {top_html} |\n")
            f.write("\n")

if __name__ == "__main__":
    resolve_sources()
