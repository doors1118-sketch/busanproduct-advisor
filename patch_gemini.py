import re

with open("app/gemini_engine.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Add cache
text = text.replace(
    "_last_generation_meta = {}",
    "_last_generation_meta = {}\n\nfrom cachetools import TTLCache\n_mcp_cache = TTLCache(maxsize=100, ttl=3600)"
)

# 2. Add [SERVER_TABLE_PLACEHOLDER]
text = text.replace(
    'answer += f"\\n\\n---\\n{server_table}"\n        \n        if generation_meta is not None',
    'if "[SERVER_TABLE_PLACEHOLDER]" in answer:\n            answer = answer.replace("[SERVER_TABLE_PLACEHOLDER]", server_table)\n        else:\n            answer += f"\\n\\n---\\n{server_table}"\n        \n        if generation_meta is not None'
)

# 3. Add Tier 0 and Tier 2 functions before _chat_v144
functions = """

def _execute_tier_0_fast_track(user_message: str, history: list, api_status, progress_callback=None) -> tuple[str, list]:
    import time
    import company_api
    start_time = time.time()
    
    if progress_callback:
        progress_callback("⚡ [Tier 0] 초고속 지역업체 검색 중...")
        
    query = user_message
    tool_start = time.time()
    try:
        raw_result = company_api.search_local_company_by_product(query)
    except Exception as e:
        import json
        raw_result = json.dumps({"error": str(e)})
        
    tool_elapsed = int((time.time() - tool_start) * 1000)
    
    all_tool_results = [{
        "tool_name": "search_local_company_by_product",
        "status": "success" if "error" not in raw_result else "failed",
        "result": raw_result,
        "elapsed_ms": tool_elapsed
    }]
    
    template = (
        "### 1. 질문의도 파악\\n"
        "- 입력하신 질문은 계약 가능 여부 판단이 아니라, 품목 기준 부산 지역업체 후보 검색 요청으로 분류했습니다.\\n\\n"
        "### 2. 지역업체 후보 소개\\n"
        "- 아래 후보는 조달등록·정책기업·쇼핑몰/MAS·인증 여부를 기준으로 정리한 검토 후보입니다.\\n\\n"
        "[SERVER_TABLE_PLACEHOLDER]\\n\\n"
        "### 3. 확인 필요사항\\n"
        "- 실제 계약 전 품목 적합성, 조달등록 상태, 종합쇼핑몰/MAS 등록 여부, 정책기업 인증 유효성, 기관 내부 기준을 확인해야 합니다.\\n"
        "- 본 안내는 후보 정보 제공이며 계약 가능 여부를 자동 확정하지 않습니다."
    )
    
    generation_meta = {
        "model_used": "bypass_tier_0",
        "model_decision_reason": "Tier 0 (Fast Track): LLM 및 MCP 전면 우회",
        "tier_resolved": 0,
        "fast_track_applied": True,
        "deterministic_template_used": True,
        "company_table_allowed": True,
        "legal_conclusion_allowed": False,
        "contract_possible_auto_promoted": False,
    }
    
    api_status.mcp_status = "skipped"
    
    answer, updated_history = _finalize_answer(
        answer=template,
        history=history,
        user_message=user_message,
        all_tool_results=all_tool_results,
        api_status=api_status,
        progress_callback=progress_callback,
        generation_meta=generation_meta
    )
    return answer, updated_history

def _execute_tier_2_mandatory_mcp(user_message: str, plan: list, progress_callback=None) -> tuple[str, list, list, list]:
    import concurrent.futures
    import json
    executed = []
    missing = []
    results = []
    
    if progress_callback:
        progress_callback("⚖️ [Tier 2] 사전 필수 법령/매뉴얼 조회 중...")

    def fetch_mcp(tool_req):
        tool_name = tool_req["name"]
        args = tool_req["args"]
        cache_key = f"{tool_name}_{json.dumps(args, sort_keys=True)}"
        
        if cache_key in _mcp_cache:
            return tool_req, _mcp_cache[cache_key], True
            
        try:
            res_str, is_timeout = call_mcp_with_timeout(tool_name, args)
            if not is_timeout and "error" not in res_str.lower():
                _mcp_cache[cache_key] = res_str
            return tool_req, res_str, False
        except Exception as e:
            return tool_req, f"Error: {e}", False

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_mcp, req) for req in plan]
        for future in concurrent.futures.as_completed(futures):
            req, res_str, from_cache = future.result()
            tool_name = req["name"]
            
            if not res_str or "Error:" in res_str or "error" in res_str.lower() or "not found" in res_str.lower():
                missing.append(tool_name)
            else:
                executed.append(tool_name)
                
            results.append(f"[{tool_name} (Cache: {from_cache})]\\n{res_str}")
            
    mcp_context = "\\n\\n".join(results)
    return mcp_context, plan, executed, missing

def _chat_v144(
"""

text = text.replace("def _chat_v144(", functions)

# 4. Integrate into _chat_v144
routing_patch = """    from policies.model_routing_policy import classify_risk, classify_query_tier
    intent_labels = [c.label for c in intent_result.candidates] if intent_result and hasattr(intent_result, 'candidates') else []
    risk_info = classify_risk(user_message, intent_labels)
    
    query_tier = classify_query_tier(risk_info, intent_labels)
    print(f"  [ROUTING] risk_level={risk_info.get('risk_level')} query_tier={query_tier}")
    
    if query_tier == 0:
        print("  [FAST-TRACK] Tier 0 detected. Bypassing Gemini completely.")
        api_status = ApiStatus()
        return _execute_tier_0_fast_track(user_message, history, api_status, progress_callback)
        
    skip_rag_completely = False"""

text = re.sub(r'from policies\.model_routing_policy import classify_risk.*?skip_rag_completely = \(risk_info\.get\("risk_level"\) == "low" and "company_search" in guardrails\)', routing_patch, text, flags=re.DOTALL)

tier2_patch = """    else:
        print("  [RAG] Skipped completely for low-risk company search.")

    mandatory_mcp_plan = []
    mandatory_mcp_executed = []
    mandatory_mcp_missing = []
    
    if query_tier == 2:
        from policies.model_routing_policy import generate_mandatory_mcp_plan
        mandatory_mcp_plan = generate_mandatory_mcp_plan(user_message, query_tier)
        if mandatory_mcp_plan:
            mcp_context, _, mandatory_mcp_executed, mandatory_mcp_missing = _execute_tier_2_mandatory_mcp(
                user_message, mandatory_mcp_plan, progress_callback
            )
            rag_context = f"### [사전 조회된 필수 법령/매뉴얼 근거]\\n{mcp_context}\\n\\n" + rag_context

    api_status = ApiStatus()"""

text = text.replace('    else:\n        print("  [RAG] Skipped completely for low-risk company search.")\n\n    # ─── 5. 프롬프트 동적 조립 ───\n    api_status = ApiStatus()', tier2_patch)

# 5. Inject variables into _last_generation_meta
meta_patch = """    # API 레이어용 generation_meta 저장
    global _last_generation_meta
    if generation_meta is not None:
        _last_generation_meta = dict(generation_meta)
    else:
        _last_generation_meta = {
            "prompt_mode": "legacy",
            "candidate_table_source": "none",
            "legal_conclusion_allowed": False,
            "final_answer_scanned": True,
            "model_used": MODEL_ID,
        }
        
    if "query_tier" in globals() or "query_tier" in locals():
        _last_generation_meta["tier_resolved"] = locals().get("query_tier", 1)
        _last_generation_meta["mandatory_mcp_plan"] = locals().get("mandatory_mcp_plan", [])
        _last_generation_meta["mandatory_mcp_executed"] = locals().get("mandatory_mcp_executed", [])
        _last_generation_meta["mandatory_mcp_missing"] = locals().get("mandatory_mcp_missing", [])
        _last_generation_meta["answer_schema_version"] = "regional_procurement_v2"
"""

text = text.replace(
    """    # API 레이어용 generation_meta 저장
    global _last_generation_meta
    if generation_meta is not None:
        _last_generation_meta = dict(generation_meta)
    else:
        _last_generation_meta = {
            "prompt_mode": "legacy",
            "candidate_table_source": "none",
            "legal_conclusion_allowed": False,
            "final_answer_scanned": True,
            "model_used": MODEL_ID,
        }""",
    meta_patch
)

with open("app/gemini_engine.py", "w", encoding="utf-8") as f:
    f.write(text)
