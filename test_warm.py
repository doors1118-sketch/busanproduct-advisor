import requests
import json

q = "7천만원으로 컴퓨터 구매해야 한다. 가급적 지역업체랑 계약하고 싶은데 방법이 있을까?"

print("Running Run 1...")
res1 = requests.post("http://127.0.0.1:8001/chat", json={"message": q}).json()
meta1 = res1.get("meta", {})

print("Running Run 2...")
res2 = requests.post("http://127.0.0.1:8001/chat", json={"message": q}).json()
meta2 = res2.get("meta", {})

output = (
    f"Run 1: {res1.get('total_latency_ms')}ms, RAG: {res1.get('rag_elapsed_ms')}ms, "
    f"Hits: {res1.get('legal_basis_cache_hit_count')}\n"
    f"Run 2: {res2.get('total_latency_ms')}ms, RAG: {res2.get('rag_elapsed_ms')}ms, "
    f"Hits: {res2.get('legal_basis_cache_hit_count')}\n"
)

with open("warm_cache_test.txt", "w", encoding="utf-8") as f:
    f.write(output)

print(output)
