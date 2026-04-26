code = None
with open("scripts/run_staging_verification.py", "r", encoding="utf-8") as f:
    code = f.read()

# Chunk 1
c1_orig = '''        gen_meta = intercepts.get("generation_meta", {})
        result_data["model_used"] = gen_meta.get("model_used", "unknown")
        result_data["fallback_used"] = gen_meta.get("fallback_used", False)
        result_data["fallback_reason"] = gen_meta.get("fallback_reason", "")
        result_data["retry_count"] = gen_meta.get("retry_count", 0)
        result_data["flash_answer_discarded"] = gen_meta.get("flash_answer_discarded", False)
        result_data["legal_basis"] = gen_meta.get("legal_basis", [])
        result_data["claim_validation"] = gen_meta.get("claim_validation", {})
        result_data["generation_meta"] = gen_meta'''

c1_new = '''        gen_meta = intercepts.get("generation_meta", {})
        result_data["model_used"] = gen_meta.get("model_used", intercepts.get("model_selected", "unknown"))
        result_data["model_selected"] = intercepts.get("model_selected", "unknown")
        result_data["core_prompt_hash"] = intercepts.get("core_prompt_hash", "")
        result_data["prompt_prefix_hash"] = intercepts.get("prompt_prefix_hash", "")
        result_data["indexed_doc_count"] = intercepts.get("indexed_doc_count", 0)
        result_data["retrieved_doc_count"] = sum(len(res) for list_res in intercepts.get("rag_results", {}).values() for res in (list_res if isinstance(list_res, list) else [])) if intercepts.get("rag_results") else 0
        result_data["retrieval_latency_ms"] = rag_elapsed
        result_data["company_table_allowed"] = gen_meta.get("company_table_allowed", False)
        result_data["fallback_used"] = gen_meta.get("fallback_used", False)
        result_data["fallback_reason"] = gen_meta.get("fallback_reason", "")
        result_data["retry_count"] = gen_meta.get("retry_count", 0)
        result_data["flash_answer_discarded"] = gen_meta.get("flash_answer_discarded", False)
        result_data["legal_basis"] = gen_meta.get("legal_basis", [])
        result_data["claim_validation"] = gen_meta.get("claim_validation", {})
        result_data["generation_meta"] = gen_meta'''

code = code.replace(c1_orig, c1_new)

# Chunk 2
c2_orig = '''            "model_used": r.get("model_used", "unknown"),
            "fallback_used": r.get("fallback_used", False),
            "fallback_reason": r.get("fallback_reason", ""),
            "retry_count": r.get("retry_count", 0),
            "total_latency_ms": r.get("total_latency_ms", 0),'''

c2_new = '''            "model_selected": r.get("model_selected", "unknown"),
            "model_used": r.get("model_used", "unknown"),
            "fallback_used": r.get("fallback_used", False),
            "fallback_reason": r.get("fallback_reason", ""),
            "retry_count": r.get("retry_count", 0),
            "total_latency_ms": r.get("total_latency_ms", 0),
            "core_prompt_hash": r.get("core_prompt_hash", ""),
            "prompt_prefix_hash": r.get("prompt_prefix_hash", ""),
            "indexed_doc_count": r.get("indexed_doc_count", 0),
            "retrieved_doc_count": r.get("retrieved_doc_count", 0),
            "retrieval_latency_ms": r.get("retrieval_latency_ms", 0),
            "company_table_allowed": r.get("company_table_allowed", False),'''

code = code.replace(c2_orig, c2_new)

# Chunk 3
c3_orig = '''    def add_preload_info(res: dict):
        res["rag_preload_status"] = preload_status.get("rag_preload_status", "unknown")
        if "total_latency_ms" not in res:
            res["total_latency_ms"] = 0
        if "model_used" not in res:
            res["model_used"] = "unknown"
        if "fallback_used" not in res:
            res["fallback_used"] = False
        if "fallback_reason" not in res:
            res["fallback_reason"] = ""
        if "retry_count" not in res:
            res["retry_count"] = 0
        return res'''

c3_new = '''    def add_preload_info(res: dict):
        res["rag_preload_status"] = preload_status.get("rag_preload_status", "unknown")
        res["chromadb_status"] = preload_status.get("chroma_status", "unknown")
        res["bm25_status"] = preload_status.get("bm25_status", "unknown")
        for f in ["indexed_doc_count", "retrieved_doc_count", "retrieval_latency_ms"]:
            if f not in res: res[f] = 0
        if "total_latency_ms" not in res: res["total_latency_ms"] = 0
        if "model_used" not in res: res["model_used"] = "unknown"
        if "fallback_used" not in res: res["fallback_used"] = False
        if "fallback_reason" not in res: res["fallback_reason"] = ""
        if "retry_count" not in res: res["retry_count"] = 0
        if res.get("model_used") == "unknown" or not res.get("model_used"):
            res["pass"] = False
            res["failure_reason"] = str(res.get("failure_reason", "")) + " | model_used is unknown"
        if not res.get("core_prompt_hash") or not res.get("prompt_prefix_hash"):
            res["pass"] = False
            res["failure_reason"] = str(res.get("failure_reason", "")) + " | prompt hash is empty"
        if res.get("company_search_status") == "success" and not res.get("company_table_allowed"):
            res["pass"] = False
            res["failure_reason"] = str(res.get("failure_reason", "")) + " | company_table_allowed is false despite success"
        return res'''

code = code.replace(c3_orig, c3_new)

with open("scripts/run_staging_verification.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Patch applied.", flush=True)
