import json, os, datetime
from check_legal_source_updates_v0_1 import check_updates
from diff_legal_versions_v0_1 import generate_diff
from classify_legal_update_impact_v0_1 import classify_impact

base = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data'
manifest_path = os.path.join(base, 'legal_update_manifest.json')

if __name__ == "__main__":
    print("Running Dry-Run of Legal DB Update Pipeline v0.1...")
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    # Step 1: Check
    check_report = check_updates(manifest_path)
    
    # Step 2 & 3: Diff & Classify
    impacts = []
    for change in check_report['results']['changed']:
        # Find meta from manifest
        source_meta = next((m for m in manifest if m['source_id'] == change['source_id']), {})
        
        diff = generate_diff(change, manifest)
        impact = classify_impact(diff, source_meta)
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
                "active_for_rule_policy": imp['recommended_action'],
                "matched_sensitive_keywords": imp.get("matched_sensitive_keywords", [])
            } for imp in impacts if imp['requires_interpretation_review']
        ]
    }
    
    report_path = os.path.join(base, 'legal_update_pipeline_dry_run_report_v0_1.json')
    with open(report_path, "w", encoding='utf-8') as f:
        json.dump(final_report, f, ensure_ascii=False, indent=2)
        
    print("Dry-Run v0.1 Completed.")
    print(f"Output saved to {report_path}")
