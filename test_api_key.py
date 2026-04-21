import urllib.request
import json

url = "https://generativelanguage.googleapis.com/v1beta/models?key=AIzaSyDJMCFzpNGpjtpyC85deojMqR9yPl_0cPA"
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
