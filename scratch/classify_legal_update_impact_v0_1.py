import json

def classify_impact(diff_report, source_meta):
    print(f"Classifying impact for {diff_report['title']}...")
    
    # Sensitive keywords to flag for Review
    sensitive_keywords = ["수의계약", "한도", "금액", "낙찰자 결정", "경쟁", "예외", "제한"]
    
    impact_level = "low"
    matched_keywords = []
    
    for article in diff_report.get("changed_articles", []):
        for kw in sensitive_keywords:
            if kw in article:
                impact_level = "high"
                matched_keywords.append(kw)
    
    # If the rule is a core routing logic, any change is sensitive
    if source_meta.get("activation_mode") in ["core_common", "procurement_route_required"]:
        if impact_level == "low":
            impact_level = "medium" # Elevate core logic changes to at least medium
            
    impact_report = {
        "source_id": diff_report["source_id"],
        "source_title": diff_report["title"],
        "active_for_rule": source_meta.get("active_for_rule", False),
        "activation_mode": source_meta.get("activation_mode"),
        "changed_articles": diff_report.get("changed_articles", []),
        "matched_sensitive_keywords": list(set(matched_keywords)),
        "impact_level": impact_level,
        "requires_interpretation_review": True if impact_level in ["medium", "high", "critical"] else False,
        "recommended_action": "hold_rule_until_review" if impact_level in ["high", "critical"] else "auto_update_source"
    }
    return impact_report

if __name__ == "__main__":
    pass
