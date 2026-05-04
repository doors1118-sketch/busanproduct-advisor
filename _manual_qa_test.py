import requests
import json
import time
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

URL = "http://127.0.0.1:8001/chat"

scenarios = {
    "A": "7천만원으로 컴퓨터 구매해야 한다. 가급적 지역업체랑 계약하고 싶은데 방법이 있을까?",
    "B": "8천만원 물품 수의계약 가능해?",
    "C": "2천만원 컴퓨터 부산업체랑 계약하고 싶어",
    "D": "CCTV 부산업체 추천해줘"
}

def test_scenario(name, query):
    print(f"\n==================================================")
    print(f"질문 [{name}]: {query}")
    print(f"==================================================\n")
    
    start_time = time.time()
    try:
        res = requests.post(URL, json={"message": query}, timeout=60)
        res.raise_for_status()
        data = res.json()
        latency = int((time.time() - start_time) * 1000)
        
        print(f"✅ 응답 완료 (Latency: {latency}ms, Tier: {data.get('tier_resolved')})")
        print(f"   - 처리 방식: {data.get('answer_builder_used')}")
        print(f"   - 근거 확인 상태: {data.get('source_status_user_label')}")
        print("\n--- 답변 내용 ---\n")
        print(data.get('answer'))
        print("\n-----------------\n")
    except Exception as e:
        print(f"❌ 에러 발생: {e}")

if __name__ == "__main__":
    for name, query in scenarios.items():
        test_scenario(name, query)
