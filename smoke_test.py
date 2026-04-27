import os
import sys
import chromadb

sys.path.insert(0, os.path.abspath('app'))
from embedding import encode_query

client = chromadb.PersistentClient(path=".chroma_manuals")
col = client.get_collection("manuals")
res = col.query(query_embeddings=[encode_query("수의계약 유의사항")], n_results=1)

print("=== MANAUAL RAG SMOKE TEST RESULT ===")
for i, doc in enumerate(res["documents"][0]):
    print(f"[{i+1}] {doc[:150]}...")
print("=====================================")
