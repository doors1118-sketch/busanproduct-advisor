import os
import sys
import time

print("="*50)
print("RAG System Verification Report")
print("="*50)

# 1. Check ChromaDB Collections
try:
    import chromadb
    chroma_dir = "/root/advisor/app/.chroma"
    print(f"\\n1. Checking ChromaDB at {chroma_dir}...")
    if not os.path.exists(chroma_dir):
        print("❌ ERROR: .chroma directory does not exist!")
    else:
        client = chromadb.PersistentClient(path=chroma_dir)
        collections = client.list_collections()
        print(f"✅ Found {len(collections)} collections.")
        for c in collections:
            count = c.count()
            print(f"  - Collection '{c.name}': {count} documents")
            
            # 2. Perform a test query on manuals to ensure HNSW index isn't corrupt
            if c.name == "manuals":
                print(f"\\n2. Testing Vector Search on '{c.name}' collection...")
                try:
                    # Dummy vector for search testing
                    dummy_vector = [0.0] * 768  # E5 embeddings are 768 dim
                    results = c.query(query_embeddings=[dummy_vector], n_results=1)
                    if results['documents']:
                        print("✅ Vector search executed successfully. No HNSW index corruption.")
                    else:
                        print("⚠️ Vector search executed, but returned no results.")
                except Exception as e:
                    print(f"❌ ERROR during vector search: {e}")
except ImportError:
    print("❌ ERROR: chromadb module not found!")
except Exception as e:
    print(f"❌ ERROR initializing ChromaDB: {e}")

# 3. Check BM25 Index
print("\\n3. Checking BM25 Hybrid Index...")
try:
    import rank_bm25
    print("✅ rank_bm25 module is installed.")
except ImportError:
    print("❌ ERROR: rank_bm25 module is NOT installed!")

bm25_path = "/root/advisor/app/.chroma/bm25_laws_index.pkl"
if os.path.exists(bm25_path):
    size = os.path.getsize(bm25_path)
    print(f"✅ BM25 Index file exists ({size / 1024 / 1024:.2f} MB)")
else:
    print("❌ ERROR: BM25 Index file NOT found!")

# 4. Check Engine E2E
print("\\n4. Testing gemini_engine.py E2E Integration (RAG fallback)...")
try:
    sys.path.insert(0, '/root/advisor/app')
    from gemini_engine import _search_manuals
    from embedding import encode_query
    
    q_vec = encode_query("수의계약 주의사항")
    rag_res = _search_manuals("수의계약 주의사항", n_results=2, query_vector=q_vec)
    if rag_res:
        print(f"✅ E2E RAG Retrieval SUCCESS. Length: {len(rag_res)} chars")
        print(f"   Preview: {rag_res[:100]}...")
    else:
        print("❌ E2E RAG Retrieval returned empty string.")
except Exception as e:
    print(f"❌ ERROR in E2E RAG Retrieval: {e}")

print("\\n" + "="*50)
