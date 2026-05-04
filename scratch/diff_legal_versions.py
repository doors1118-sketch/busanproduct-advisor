import json

def generate_diff(old_source, new_source):
    print(f"Generating diff for {new_source['title']}...")
    # Mocking diff generation
    diff_report = {
        "source_id": new_source['source_id'],
        "title": new_source['title'],
        "diff_type": "article_text_changed",
        "changed_articles": ["제5장", "제7장"],
        "added_articles": [],
        "deleted_articles": []
    }
    return diff_report

if __name__ == "__main__":
    report = generate_diff({"source_id":"mock_id_1", "title":"지방자치단체 입찰 및 계약집행기준"}, {"source_id":"mock_id_1", "title":"지방자치단체 입찰 및 계약집행기준"})
    with open("legal_diff_report_mock.json", "w", encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
