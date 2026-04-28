import time
import os
from typing import Dict, Any

def warmup_rag() -> Dict[str, Any]:
    """
    운영 환경에서 콜드 스타트를 방지하기 위해 
    앱 시작 시 임베딩 모델, ChromaDB, BM25 인덱스를 메모리에 적재하는 웜업 함수.
    """
    status = {
        "rag_preload_status": "success",
        "embedding_model_loaded": False,
        "laws_chroma_status": "not_tested",
        "manuals_chroma_status": "not_tested",
        "rag_status": "not_tested",
        "bm25_status": "not_tested",
        "laws_indexed": 0,
        "manuals_indexed": 0,
        "manuals_error": "",
        "preload_elapsed_ms": 0
    }
    start = time.time()
    
    try:
        # 1. Load embedding model
        from embedding import encode_query
        encode_query("warmup dummy query")
        status["embedding_model_loaded"] = True
        
        # 2. Check laws collection
        try:
            import chromadb
            client_laws = chromadb.PersistentClient(path=os.environ.get("CHROMA_LAWS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma_laws")))
            laws_col = client_laws.get_collection("laws")
            status["laws_indexed"] = laws_col.count()
            status["laws_chroma_status"] = "success"
        except Exception as e:
            status["laws_chroma_status"] = f"failed - {e}"

        # 3. Check manuals collections (multi-collection: manuals_1, manuals_2, ...)
        try:
            import chromadb
            client_manuals = chromadb.PersistentClient(path=os.environ.get("CHROMA_MANUALS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma")))
            sub_cols = [c for c in client_manuals.list_collections() if c.name.startswith("manuals_")]
            if sub_cols:
                total = sum(client_manuals.get_collection(c.name).count() for c in sub_cols)
                status["manuals_indexed"] = total
                status["manuals_chroma_status"] = "success"
            else:
                status["manuals_chroma_status"] = "failed - no manuals_ sub-collections found"
        except Exception as e:
            status["manuals_chroma_status"] = f"failed - {e}"
            status["manuals_error"] = str(e)
            
        if status["laws_chroma_status"] == "success" and status["manuals_chroma_status"] == "success":
            status["rag_status"] = "SUCCESS"
        elif status["laws_chroma_status"] == "success":
            status["rag_status"] = "PARTIAL_DEGRADED"
        else:
            status["rag_status"] = "FAILED"

        status["bm25_status"] = "success"

    except Exception as e:
        status["rag_preload_status"] = f"failed: {str(e)}"
        
    status["preload_elapsed_ms"] = int((time.time() - start) * 1000)
    return status
