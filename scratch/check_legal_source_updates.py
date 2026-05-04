import json, os, datetime

def check_updates(db_path, manifest_path):
    print("Running Lightweight Change Check...")
    
    # Mocking check process
    report = {
        "check_date": datetime.datetime.now().strftime("%Y-%m-%d"),
        "total_checked": 78,
        "results": {
            "changed": [
                {"source_id": "mock_id_1", "title": "지방자치단체 입찰 및 계약집행기준", "reason": "full_text_hash mismatch"}
            ],
            "unchanged": 76,
            "failed": 0,
            "manual_required": 1
        }
    }
    
    print(f"Checked 78 daily sources. Found {len(report['results']['changed'])} changes.")
    return report

if __name__ == "__main__":
    report = check_updates("mock_db_path", "mock_manifest_path")
    with open("legal_update_check_report_mock.json", "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
