lines = []
with open("scripts/run_staging_verification.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
skip = False
for line in lines:
    if "def add_preload_info(res: dict):" in line:
        skip = True
        new_lines.append(line)
        new_lines.append('''        res["rag_preload_status"] = preload_status.get("rag_preload_status", "unknown")
        res["laws_chromadb_status"] = preload_status.get("laws_chroma_status", "unknown")
        res["manuals_chromadb_status"] = preload_status.get("manuals_chroma_status", "unknown")
        res["rag_status"] = preload_status.get("rag_status", "unknown")
        res["bm25_status"] = preload_status.get("bm25_status", "unknown")
        import os
        res["manuals_rag_enabled"] = os.environ.get("RAG_MANUALS_ENABLED", "true")
        res["laws_indexed_doc_count"] = preload_status.get("laws_indexed", 0)
        res["manuals_indexed_doc_count"] = preload_status.get("manuals_indexed", 0)
        res["manuals_error_message"] = preload_status.get("manuals_error", "")
        
        fails = 0
        if os.path.exists("manuals_ingest_failures.json"):
            try:
                import json
                with open("manuals_ingest_failures.json", "r", encoding="utf-8") as _jf:
                    fails = len(json.load(_jf))
            except: pass
        res["manuals_ingest_failed_count"] = fails
        
        res["shopping_mall_status"] = res.get("shopping_mall_status", "unknown")
        res["shopping_mall_elapsed_ms"] = res.get("shopping_mall_elapsed_ms", 0)
        res["tool_timeout_sources"] = res.get("tool_timeout_sources", [])
        
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
        return res\n''')
        continue
    
    if skip:
        if "return res" in line:
            skip = False
        continue
        
    new_lines.append(line)

with open("scripts/run_staging_verification.py", "w", encoding="utf-8") as f:
    f.writelines(new_lines)
