"""Gemini API 키 테스트 (환경변수 사용)"""
import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("❌ GEMINI_API_KEY 환경변수가 설정되지 않았습니다.")
    exit(1)

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
try:
    resp = urllib.request.urlopen(url)
    data = json.loads(resp.read())
    models = data.get("models", [])
    for m in models[:5]:
        print(m["name"])
    print(f"... 총 {len(models)}개 모델 사용 가능")
    print("\n✅ API 키 정상 작동!")
except Exception as e:
    print(f"❌ 오류: {e}")
