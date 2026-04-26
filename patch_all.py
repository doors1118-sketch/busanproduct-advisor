import os

def check(f):
    with open(f, "r", encoding="utf-8") as file: return file.read()
def write(f, content):
    with open(f, "w", encoding="utf-8") as file: file.write(content)

# 1. app/ingest_manuals.py
c = check("app/ingest_manuals.py")
c = c.replace('CHROMA_DIR = os.path.join(_root, ".chroma")', 'CHROMA_DIR = os.environ.get("CHROMA_MANUALS_DIR", os.path.join(_root, ".chroma_manuals"))')
c_err = r'''    except Exception as e:
        print(f"  [WARN] PDF read failed: {pdf_path} - {e}")
        import json
        fail_file = "manuals_ingest_failures.json"
        fails = []
        if os.path.exists(fail_file):
            try:
                with open(fail_file, "r", encoding="utf-8") as jf: fails = json.load(jf)
            except: pass
        fails.append({"file": pdf_path, "error": str(e)})
        with open(fail_file, "w", encoding="utf-8") as jf: json.dump(fails, jf, ensure_ascii=False, indent=2)'''
c = c.replace(r'''    except Exception as e:
        print(f"  [WARN] PDF read failed: {pdf_path} - {e}")''', c_err)
write("app/ingest_manuals.py", c)

# 2. app/ingest_laws.py
c = check("app/ingest_laws.py")
c = c.replace('CHROMA_DIR = os.path.join(_root, ".chroma")', 'CHROMA_DIR = os.environ.get("CHROMA_LAWS_DIR", os.path.join(_root, ".chroma_laws"))')
write("app/ingest_laws.py", c)

# 3. app/ingest_pps_qa.py
c = check("app/ingest_pps_qa.py")
c = c.replace('CHROMA_DIR = os.path.join(os.path.dirname(__file__), ".chroma")', 'CHROMA_DIR = os.environ.get("CHROMA_MANUALS_DIR", os.path.join(os.path.dirname(__file__), ".chroma_manuals"))')
write("app/ingest_pps_qa.py", c)

# 4. app/gemini_engine.py
c = check("app/gemini_engine.py")

c_rag1 = r'''        chroma_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma")
        client = chromadb.PersistentClient(path=chroma_dir)'''
c_rag1_new = r'''        chroma_dir = os.environ.get("CHROMA_MANUALS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma_manuals"))
        client = chromadb.PersistentClient(path=chroma_dir)'''
c = c.replace(c_rag1, c_rag1_new)

c = c.replace(r'''    def search_law():
        return _search_law_rag(query, agency_type=agency_type)''', r'''    def search_law():
        if os.environ.get("RAG_LAWS_ENABLED", "true").lower() == "false": return ""
        return _search_law_rag(query, agency_type=agency_type)''')

c = c.replace(r'''    def search_manual():
        return _search_manuals(query, query_vector=query_vector)''', r'''    def search_manual():
        if os.environ.get("RAG_MANUALS_ENABLED", "true").lower() == "false": return ""
        return _search_manuals(query, query_vector=query_vector)''')

c_timeout = r'''        elif name == "search_local_company_by_product":
            q = args.get("query", "")
            def _f():
                data = company_api.search_by_product(q)
                company_api.last_search_results = data
                company_api.last_search_query = f"품목: {q}"
                return format_company_for_llm(data, max_results=10)
            return _run_with_timeout(_f)
        elif name == "search_local_company_by_license":
            q = args.get("query", "")
            def _f():
                data = company_api.search_by_license(q)
                company_api.last_search_results = data
                company_api.last_search_query = f"면허: {q}"
                return format_company_for_llm(data, max_results=10)
            return _run_with_timeout(_f)
        elif name == "search_local_company_by_category":
            q = args.get("query", "")
            def _f():
                data = company_api.search_by_category(q)
                company_api.last_search_results = data
                company_api.last_search_query = f"분류: {q}"
                return format_company_for_llm(data, max_results=10)
            return _run_with_timeout(_f)
        # ── 종합쇼핑몰 ──
        elif name == "search_shopping_mall":
            import shopping_mall
            q = args.get("query", "")
            def _f():
                data = shopping_mall.search_mall_products(q, busan_only=True)
                shopping_mall.last_mall_results = data
                shopping_mall.last_mall_query = q
                return shopping_mall.format_mall_results(data, max_results=5)
            return _run_with_timeout(_f)'''
            
c_old_timeout = r'''        elif name == "search_local_company_by_product":
            q = args.get("query", "")
            data = company_api.search_by_product(q)
            company_api.last_search_results = data
            company_api.last_search_query = f"품목: {q}"
            return format_company_for_llm(data, max_results=10)
        elif name == "search_local_company_by_license":
            q = args.get("query", "")
            data = company_api.search_by_license(q)
            company_api.last_search_results = data
            company_api.last_search_query = f"면허: {q}"
            return format_company_for_llm(data, max_results=10)
        elif name == "search_local_company_by_category":
            q = args.get("query", "")
            data = company_api.search_by_category(q)
            company_api.last_search_results = data
            company_api.last_search_query = f"분류: {q}"
            return format_company_for_llm(data, max_results=10)
        # ── 종합쇼핑몰 ──
        elif name == "search_shopping_mall":
            import shopping_mall
            q = args.get("query", "")
            data = shopping_mall.search_mall_products(q, busan_only=True)
            shopping_mall.last_mall_results = data
            shopping_mall.last_mall_query = q
            return shopping_mall.format_mall_results(data, max_results=5)'''

c = c.replace(c_old_timeout, c_timeout)
write("app/gemini_engine.py", c)

# 5. run_staging_verification.py
c = check("scripts/run_staging_verification.py")

c_json_orig = r'''    def add_preload_info(res: dict):
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

c_json_new = r'''    def add_preload_info(res: dict):
        res["rag_preload_status"] = preload_status.get("rag_preload_status", "unknown")
        res["laws_chromadb_status"] = preload_status.get("laws_chroma_status", "unknown")
        res["manuals_chromadb_status"] = preload_status.get("manuals_chroma_status", "unknown")
        res["rag_status"] = preload_status.get("rag_status", "unknown")
        res["bm25_status"] = preload_status.get("bm25_status", "unknown")
        res["manuals_rag_enabled"] = os.environ.get("RAG_MANUALS_ENABLED", "true")
        res["laws_indexed_doc_count"] = preload_status.get("laws_indexed", 0)
        res["manuals_indexed_doc_count"] = preload_status.get("manuals_indexed", 0)
        res["manuals_error_message"] = preload_status.get("manuals_error", "")
        
        # calculate manual ingest failures
        fails = 0
        if os.path.exists("manuals_ingest_failures.json"):
            try:
                import json
                with open("manuals_ingest_failures.json", "r", encoding="utf-8") as f:
                    fails = len(json.load(f))
            except: pass
        res["manuals_ingest_failed_count"] = fails
        
        # For mock/tests that append tool_timeout_sources
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
        return res'''

c = c.replace(c_json_orig, c_json_new)

# handle fetching laws vs manuals chroma db stats inside warmup_rag in scripts/warmup.py
write("scripts/run_staging_verification.py", c)

print("Patch applied globally.", flush=True)
