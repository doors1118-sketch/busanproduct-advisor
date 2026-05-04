import json
import os
import sys
from collections import defaultdict

# Add current dir to sys.path to import app module
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from app.gateway.db.reader import ReadOnlyDatabase

QUERY_EXPANSION = {
    "지역제한": ["지역제한", "제한경쟁", "주된 영업소"],
    "제한경쟁": ["제한경쟁", "주된 영업소"],
    "수의계약": ["수의계약", "소액수의"],
    "1인 견적": ["1인 견적", "수의계약"],
    "2인 이상 견적": ["2인 이상", "안내공고", "수의계약"],
    "MAS 2단계경쟁": ["2단계경쟁", "다수공급자계약"],
    "2단계경쟁": ["2단계경쟁", "다수공급자계약"],
    "지역업체 참여도": ["참여도", "지역업체 가점", "지역업체"],
    "지역의무공동도급": ["지역의무공동도급", "공동수급"],
    "종합평가방식": ["종합평가방식", "다수공급자계약"]
}

CATALOG_PATH = "local_purchase_support_rule_catalog.json"
DB_PATH = "app/data/legal_db_v0_1_3.sqlite"
MAP_OUTPUT_PATH = "purchase_support_rule_source_map.json"
REPORT_OUTPUT_PATH = "purchase_support_source_chain_discovery_report.md"

def resolve_sources():
    with open(CATALOG_PATH, "r", encoding="utf-8") as f:
        catalog = json.load(f)

    db = ReadOnlyDatabase(DB_PATH)
    
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
        query_terms = rule.get("legal_basis_query_terms", [])
        
        # 1. Primary Sources Matching
        primary_sources = []
        matched_original_terms = set()
        matched_expanded_terms = set()
        unmatched_terms = set(query_terms)
        
        for term in query_terms:
            search_terms = QUERY_EXPANSION.get(term, [term])
            term_matched = False
            for s_term in search_terms:
                query = """
                SELECT source_id, normalized_title, source_name, review_status
                FROM legal_source
                WHERE (normalized_title LIKE ? OR source_name LIKE ?)
                AND review_status NOT IN ('wrong_match', 'needs_manual_source')
                """
                rows = db.execute(query, (f"%{s_term}%", f"%{s_term}%"))
                
                if rows:
                    term_matched = True
                    if s_term == term:
                        matched_original_terms.add(s_term)
                    else:
                        matched_expanded_terms.add(s_term)
                    for r in rows:
                        primary_sources.append(r)
            if term_matched and term in unmatched_terms:
                unmatched_terms.remove(term)
        
        # Deduplicate primary sources
        unique_primary = {}
        for ps in primary_sources:
            unique_primary[ps["source_id"]] = ps
        
        primary_source_ids = list(unique_primary.keys())
        
        # 2. Related Sources Matching
        related_source_ids = []
        if unique_primary:
            primary_titles = [ps["normalized_title"] for ps in unique_primary.values()]
            placeholders = ",".join(["?"] * len(primary_titles))
            
            rel_query = f"""
            SELECT DISTINCT s.source_id, s.normalized_title
            FROM legal_relation r
            JOIN legal_source s ON (s.normalized_title = r.source_title OR s.normalized_title = r.target_title)
            WHERE (r.source_title IN ({placeholders}) OR r.target_title IN ({placeholders}))
            AND s.source_id NOT IN ({",".join(["?"] * len(primary_source_ids))})
            AND s.review_status NOT IN ('wrong_match', 'needs_manual_source')
            AND r.review_status NOT IN ('wrong_match', 'needs_manual_source')
            ORDER BY CASE WHEN r.review_status = 'verified' THEN 0 ELSE 1 END
            """
            
            params = tuple(primary_titles + primary_titles + primary_source_ids)
            rel_rows = db.execute(rel_query, params)
            related_source_ids = [r["source_id"] for r in rel_rows]
            
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
        has_verified = any(ps["review_status"] == "verified" for ps in unique_primary.values())
        
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
                if has_verified:
                    status = "mapped_verified"
                    summary["mapped_verified"] += 1
                else:
                    status = "mapped_candidate"
                    summary["mapped_candidate"] += 1
        
        rule_source_map[rule_id] = {
            "rule_id": rule_id,
            "display_name": rule["display_name"],
            "category": rule["category"],
            "primary_source_ids": primary_source_ids,
            "related_source_ids": related_source_ids,
            "matched_query_terms": {
                "original": list(matched_original_terms),
                "expanded": list(matched_expanded_terms)
            },
            "unmatched_query_terms": list(unmatched_terms),
            "numeric_parameters": numeric_parameters,
            "source_chain_status": status,
            "primary_source_details": [{"id": k, "title": v["normalized_title"], "status": v["review_status"]} for k, v in unique_primary.items()]
        }

    # Write Map JSON
    with open(MAP_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rule_source_map, f, ensure_ascii=False, indent=2)
        
    # Write Report MD
    with open(REPORT_OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write("# Phase 9.2-B Source Chain Discovery Report\n\n")
        
        f.write("## 1. Mapping Summary\n")
        f.write(f"- **Total Rules**: {summary['total_rules']}\n")
        f.write(f"- **Mapped Verified**: {summary['mapped_verified']}\n")
        f.write(f"- **Mapped Candidate**: {summary['mapped_candidate']}\n")
        f.write(f"- **Partial Mapped**: {summary['partial_mapped']}\n")
        f.write(f"- **Pending Resolution**: {summary['pending_resolution']}\n")
        f.write(f"- **Company API / Outside DB**: {summary['company_api']}\n\n")
        
        f.write("## 2. Rule Source Mapping Details\n\n")
        
        categories = defaultdict(list)
        for r in rule_source_map.values():
            categories[r["category"]].append(r)
            
        for cat, rules in categories.items():
            f.write(f"### Category: `{cat}`\n\n")
            f.write("| Rule ID | Name | Status | Verified / Cand. Sources | Primary Titles | Unmatched Terms | Numeric Params Pending |\n")
            f.write("|---------|------|--------|--------------------------|----------------|-----------------|------------------------|\n")
            for r in rules:
                verified_cnt = sum(1 for ps in r["primary_source_details"] if ps["status"] == "verified")
                candidate_cnt = len(r["primary_source_ids"]) - verified_cnt
                
                titles_html = "<br>".join([ps["title"] for ps in r["primary_source_details"]]) if r["primary_source_details"] else "None"
                unmatched = ", ".join(r["unmatched_query_terms"]) if r["unmatched_query_terms"] else "None"
                numeric_pending = "Yes" if r["numeric_parameters"] else "No"
                
                f.write(f"| `{r['rule_id']}` | {r['display_name']} | `{r['source_chain_status']}` | {verified_cnt} / {candidate_cnt} | {titles_html} | {unmatched} | {numeric_pending} |\n")
            f.write("\n")

if __name__ == "__main__":
    resolve_sources()
