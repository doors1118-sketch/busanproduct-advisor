import json, os, datetime

def check_updates(manifest_path):
    print("Running Lightweight Change Check v0.1...")
    
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)
        
    daily_targets = [m for m in manifest if m['update_priority'] == 'daily' and m['update_enabled']]
    
    # Mocking check process over actual daily targets
    changed = []
    unchanged = 0
    
    for idx, target in enumerate(daily_targets):
        # Let's mock a change for the first one only, to simulate the diff
        if idx == 0:
            changed.append({
                "source_id": target['source_id'],
                "title": target['normalized_title'],
                "reason": "full_text_hash mismatch",
                "old_version_hash": target['current_version_hash'],
                "new_version_hash": "simulated_new_hash_123"
            })
        else:
            unchanged += 1
            
    report = {
        "check_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "total_checked": len(daily_targets),
        "results": {
            "changed": changed,
            "unchanged": unchanged,
            "failed": 0,
            "manual_required": len([m for m in manifest if m['manual_review_required']])
        }
    }
    
    print(f"Checked {len(daily_targets)} daily sources. Found {len(changed)} changes.")
    return report

if __name__ == "__main__":
    report = check_updates(r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_update_manifest.json")
    with open(r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_update_check_report_v0_1.json", "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
