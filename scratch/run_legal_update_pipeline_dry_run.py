import json, datetime

# Mocked functions representing pipeline steps
def check_updates():
    return {
        "check_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "total_checked": 78,
        "results": {
            "changed": [
                {"source_id": "src_1", "title": "지방자치단체 입찰 및 계약집행기준", "reason": "full_text_hash mismatch"}
            ],
            "unchanged": 77,
            "failed": 0,
            "manual_required": 0
        }
    }

def generate_diff(source_info):
    return {
        "source_id": source_info['source_id'],
        "title": source_info['title'],
        "diff_type": "article_text_changed",
        "changed_articles": ["제5장 수의계약"],
        "added_articles": [],
        "deleted_articles": []
    }

def classify_impact(diff_report):
    # If the word '수의계약' is in the diff, trigger high impact
    has_critical_changes = any("수의계약" in art for art in diff_report['changed_articles'])
    
    impact_level = "high" if has_critical_changes else "low"
    
    return {
        "source_id": diff_report["source_id"],
        "source_title": diff_report["title"],
        "impact_level": impact_level,
        "requires_interpretation_review": True if impact_level in ["high", "critical"] else False,
        "recommended_action": "fail_closed_until_review" if impact_level in ["high", "critical"] else "auto_update_source"
    }

if __name__ == "__main__":
    print("Running Dry-Run of Legal DB Update Pipeline...")
    
    # Step 1: Check
    check_report = check_updates()
    
    # Step 2 & 3: Diff & Classify
    impacts = []
    for change in check_report['results']['changed']:
        diff = generate_diff(change)
        impact = classify_impact(diff)
        impacts.append(impact)
        
    # Generate Dry Run Report
    final_report = {
        "pipeline_run_date": datetime.datetime.now().isoformat(),
        "step_1_lightweight_check": check_report,
        "step_2_diff_and_classification": impacts,
        "step_3_review_queue_routing": [
            {
                "queue_id": f"q_{imp['source_id']}_{datetime.datetime.now().strftime('%Y%m%d')}",
                "source_title": imp['source_title'],
                "status": "pending_review",
                "active_for_rule_policy": "hold_answers_temporarily"
            } for imp in impacts if imp['requires_interpretation_review']
        ]
    }
    
    with open(r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_update_dry_run_report.json", "w", encoding='utf-8') as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)
        
    print("Dry-Run Completed. Output saved to app/data/legal_update_dry_run_report.json")
