import json
import os
try:
    with open(r'app\data\_checkpoint.json', 'r', encoding='utf-8') as f:
        d = json.load(f)
    print(f"진행률: {len(d['completed_seeds'])}/37")
    print(f"최근 완료: {d['completed_seeds'][-5:]}")
except Exception as e:
    print(f"오류: {e}")
