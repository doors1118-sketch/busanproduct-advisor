import json

def classify_impact(diff_report, source_meta):
    print(f"Classifying impact for {diff_report['title']}...")
    
    # Mocking classification logic based on sensitive keywords (amount, exception, procedure)
    sensitive_keywords = ["수의계약", "한도", "금액", "낙찰자 결정"]
    impact_level = "low"
    
    # Simulating finding a sensitive keyword in the changed articles
    for article in diff_report.get("changed_articles", []):
        impact_level = "high"  # Mocked logic
        break
        
    impact_report = {
        "source_id": diff_report["source_id"],
        "source_title": diff_report["title"],
        "active_for_rule": source_meta.get("active_for_rule", True),
        "activation_mode": source_meta.get("activation_mode", "core_common"),
        "changed_articles": diff_report.get("changed_articles", []),
        "impact_level": impact_level,
        "requires_interpretation_review": True if impact_level in ["high", "critical"] else False,
        "recommended_action": "hold_rule_until_review" if impact_level in ["high", "critical"] else "auto_update_source"
    }
    return impact_report

if __name__ == "__main__":
    impact = classify_impact(
        {"source_id":"mock_id_1", "title":"지방자치단체 입찰 및 계약집행기준", "changed_articles":["제5장 수의계약"]},
        {"active_for_rule": True, "activation_mode": "core_common"}
    )
    with open("legal_impact_classification_mock.json", "w", encoding='utf-8') as f:
        json.dump(impact, f, ensure_ascii=False, indent=2)
