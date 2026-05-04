import json

def generate_diff(change_info, manifest):
    print(f"Generating diff for {change_info['title']}...")
    
    # Mocking diff logic but now referencing hash differences
    # In a real scenario, this would compare old_article_hash and new_article_hash
    
    # We simulate a sensitive change for testing the classifier
    diff_report = {
        "source_id": change_info['source_id'],
        "title": change_info['title'],
        "old_version_hash": change_info['old_version_hash'],
        "new_version_hash": change_info['new_version_hash'],
        "diff_type": "article_text_changed",
        "changed_articles": ["제5장 (수의계약 한도액 개정)", "제7장"],
        "added_articles": [],
        "deleted_articles": []
    }
    return diff_report

if __name__ == "__main__":
    report = generate_diff({"source_id":"src", "title":"title", "old_version_hash":"old", "new_version_hash":"new"}, [])
    print(json.dumps(report, ensure_ascii=False, indent=2))
