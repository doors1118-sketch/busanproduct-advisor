"""
Local RAG Smoke Test
- laws, manuals, innovation ChromaDB 컬렉션 존재 여부 및 검색 테스트
- MCP는 법령 판단의 source of truth. laws RAG는 advisory_context_only.
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from embedding import get_query_embedding_fn

CHROMA_APP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", ".chroma")
CHROMA_MANUALS_DIR = os.environ.get(
    "CHROMA_MANUALS_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", ".chroma"),
)

SMOKE_QUERIES = {
    "laws": "수의계약 한도",
    "manuals": "수의계약 유의사항",
    "innovation": "공기청정기",
}


def check_collection(chroma_dir: str, collection_name: str, query: str, n_results: int = 3) -> dict:
    """ChromaDB 컬렉션 존재 여부 및 검색 결과 확인."""
    result = {
        "collection": collection_name,
        "chroma_dir": chroma_dir,
        "status": "not_found",
        "doc_count": 0,
        "retrieved_count": 0,
        "retrieval_latency_ms": 0,
        "query": query,
        "sample_text": "",
        "error": "",
    }

    try:
        import chromadb
        if not os.path.isdir(chroma_dir):
            result["status"] = "chroma_dir_missing"
            result["error"] = f"Directory not found: {chroma_dir}"
            return result

        client = chromadb.PersistentClient(path=chroma_dir)
        try:
            embedding_fn = get_query_embedding_fn()
            col = client.get_collection(collection_name, embedding_function=embedding_fn)
        except Exception:
            result["status"] = "collection_not_found"
            result["error"] = f"Collection [{collection_name}] does not exist"
            return result

        result["doc_count"] = col.count()
        if result["doc_count"] == 0:
            result["status"] = "empty"
            return result

        # retrieval test
        st = time.time()
        res = col.query(query_texts=[query], n_results=n_results)
        elapsed = int((time.time() - st) * 1000)

        result["retrieval_latency_ms"] = elapsed

        if res["documents"] and res["documents"][0]:
            result["retrieved_count"] = len(res["documents"][0])
            result["sample_text"] = res["documents"][0][0][:200]
            result["status"] = "success"
        else:
            result["status"] = "no_results"

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def run_smoke_test() -> dict:
    """전체 RAG smoke test 실행."""
    results = {}

    # 1. laws
    laws_result = check_collection(CHROMA_APP_DIR, "laws", SMOKE_QUERIES["laws"])
    laws_result["role"] = "advisory_context_only"
    laws_result["note"] = "MCP가 법령 판단의 source of truth. laws RAG는 보조 컨텍스트 전용."
    results["laws"] = laws_result

    # 2. manuals (멀티컬렉션: manuals_1, manuals_2, ...)
    manuals_result = {
        "chroma_dir": os.path.abspath(CHROMA_MANUALS_DIR),
        "status": "collection_not_found",
        "doc_count": 0,
        "retrieved_count": 0,
        "retrieval_latency_ms": 0,
    }
    try:
        import chromadb
        from embedding import get_query_embedding_fn
        embedding_fn = get_query_embedding_fn()
        client = chromadb.PersistentClient(path=CHROMA_MANUALS_DIR)
        sub_cols = [c for c in client.list_collections() if c.name.startswith("manuals_")]
        if not sub_cols:
            manuals_result["status"] = "collection_not_found"
            manuals_result["error"] = "No manuals_ sub-collections found"
        else:
            total_docs = 0
            all_docs = []
            for col_info in sub_cols:
                col = client.get_collection(col_info.name, embedding_function=embedding_fn)
                cnt = col.count()
                total_docs += cnt
                res = col.query(query_texts=[SMOKE_QUERIES["manuals"]], n_results=3)
                if res["documents"] and res["documents"][0]:
                    for doc, dist in zip(res["documents"][0], res["distances"][0]):
                        all_docs.append({"doc": doc, "distance": dist})
            manuals_result["doc_count"] = total_docs
            all_docs.sort(key=lambda x: x["distance"])
            manuals_result["retrieved_count"] = min(len(all_docs), 3)
            if all_docs:
                manuals_result["sample_text"] = all_docs[0]["doc"][:200]
                manuals_result["status"] = "success"
            else:
                manuals_result["status"] = "no_results"
            manuals_result["sub_collection_count"] = len(sub_cols)
    except Exception as e:
        manuals_result["status"] = "error"
        manuals_result["error"] = str(e)
    results["manuals"] = manuals_result

    # 3. innovation
    innovation_result = check_collection(CHROMA_APP_DIR, "innovation", SMOKE_QUERIES["innovation"])
    results["innovation"] = innovation_result

    return results


def print_summary(results: dict):
    """결과 요약 출력."""
    print("\n" + "=" * 60)
    print("  LOCAL RAG SMOKE TEST RESULTS")
    print("=" * 60)

    for name, r in results.items():
        status_icon = "[OK]" if r["status"] == "success" else "[WARN]" if r["status"] in ("empty", "no_results") else "[FAIL]"
        print(f"\n  {status_icon} {name.upper()}")
        print(f"     status:            {r['status']}")
        print(f"     doc_count:         {r['doc_count']}")
        print(f"     retrieved_count:   {r['retrieved_count']}")
        print(f"     latency_ms:        {r['retrieval_latency_ms']}")
        if r.get("role"):
            print(f"     role:              {r['role']}")
        if r.get("error"):
            print(f"     error:             {r['error']}")
        if r.get("sample_text"):
            print(f"     sample:            {r['sample_text'][:100]}...")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    results = run_smoke_test()
    print_summary(results)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_rag_smoke_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n  Results saved to: {out_path}")
