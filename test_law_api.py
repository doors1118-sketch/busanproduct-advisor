"""법제처 API 연결 테스트"""
import sys
sys.path.insert(0, "app")
from law_api_client import search_law, search_interpretations, get_law_text
import json

print("=== 1. search_law test ===")
results = search_law("지방계약법")
print(f"Results count: {len(results)}")
if results:
    for r in results[:3]:
        print(json.dumps(r, ensure_ascii=False, indent=2))
else:
    print("EMPTY - API may still be blocked")

print("\n=== 2. search_interpretations test ===")
interps = search_interpretations("수의계약")
print(f"Results count: {len(interps)}")
if interps:
    for i in interps[:2]:
        print(json.dumps(i, ensure_ascii=False, indent=2))
