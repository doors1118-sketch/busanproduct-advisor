import time
from typing import Dict, Any

def warmup_rag() -> Dict[str, Any]:
    """
    운영 환경에서 콜드 스타트를 방지하기 위해 
    앱 시작 시 임베딩 모델, ChromaDB, BM25 인덱스를 메모리에 적재하는 웜업 함수.
    """
    status = {
        "rag_preload_status": "success",
        "embedding_model_loaded": False,
        "chroma_status": "not_tested",
        "bm25_status": "not_tested",
        "preload_elapsed_ms": 0
    }
    start = time.time()
    
    try:
        # 1. Load embedding model
        from embedding import encode_query
        encode_query("warmup dummy query")
        status["embedding_model_loaded"] = True
        
        # 2. Dummy Retrieval (ChromaDB & BM25 로드 유발)
        from gemini_engine import _parallel_rag_search
        rag_res = _parallel_rag_search("부산시청 수의계약 한도", agency_type="busan_city")
        
        if any(rag_res.values()):
            status["chroma_status"] = "success"
            status["bm25_status"] = "success" # search_laws 내부에서 BM25 로드
        else:
            status["chroma_status"] = "failed: returned empty"
            status["bm25_status"] = "failed: returned empty"
            status["rag_preload_status"] = "partial_failure"
            
    except Exception as e:
        status["rag_preload_status"] = f"failed: {str(e)}"
        
    status["preload_elapsed_ms"] = int((time.time() - start) * 1000)
    return status
