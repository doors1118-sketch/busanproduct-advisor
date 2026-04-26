import chromadb
import time

print("\n--- CHROMA DB STATUS ---")
client = chromadb.PersistentClient(path="C:\\dev\\busan_procurement_chatbot\\.chroma")
collections = client.list_collections()
print(f"collection_count: {len(collections)}")
print(f"tenant_status: default_tenant connected")
total_docs = 0
for c in collections:
    total_docs += c.count()
print(f"indexed_doc_count: {total_docs}")

try:
    c = client.get_collection("laws")
    start = time.time()
    res = c.query(query_texts=["지방계약법 수의계약"], n_results=2)
    latency = int((time.time() - start) * 1000)
    print(f"retrieval_test_query: '지방계약법 수의계약'")
    print(f"retrieved_doc_count: {sum(len(d) for d in res.get('documents', []))}")
    print(f"retrieval_latency_ms: {latency}")
    print("rag_status: success")
except Exception as e:
    print(f"rag_status: failed - {e}")
