import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

scenarios = ['a', 'b', 'c', 'd']
data = {}

for s in scenarios:
    with open(f'scenario_{s}_raw.json', encoding='utf-8-sig') as f:
        data[s] = json.load(f)

latency_limits = {
    'a': 45000,
    'b': 10000,
    'c': 30000,
    'd': 10000
}

all_pass = True

print("=== Phase 5 Stage 3 Verification ===")

for s in scenarios:
    print(f"\n[Scenario {s.upper()}]")
    d = data[s]
    
    # Check required fields
    required_fields = [
        "tier_resolved", "answer_schema_version", "answer_builder_used",
        "answer_builder_elapsed_ms", "answer_builder_network_call_count",
        "latency_ms", "total_latency_ms", "rag_elapsed_ms", "model_elapsed_ms",
        "rewrite_elapsed_ms", "mcp_preflight_elapsed_ms",
        "legal_basis_cache_used", "legal_basis_cache_hit_count",
        "legal_basis_cache_miss_count", "source_status", "source_status_user_label",
        "candidate_table_source", "candidate_counts_by_type",
        "mandatory_mcp_plan", "mandatory_mcp_executed", "mandatory_mcp_missing",
        "forbidden_patterns_remaining_after_rewrite",
        "legal_conclusion_allowed", "contract_possible_auto_promoted",
        "production_deployment", "legal_basis_table_rendered",
        "raw_tool_names_hidden_from_answer", "user_facing_source_labels_used"
    ]
    
    missing_fields = [f for f in required_fields if f not in d or d[f] is None]
    if missing_fields:
        print(f"  FAIL: Missing fields: {missing_fields}")
        all_pass = False
    else:
        print("  PASS: All required fields present.")

    # Check Answer Builder constraints
    nw_calls = d.get('answer_builder_network_call_count', -1)
    if nw_calls > 0:
        print(f"  FAIL: answer_builder_network_call_count = {nw_calls} (> 0)")
        all_pass = False
    elif nw_calls == 0:
        print("  PASS: answer_builder_network_call_count = 0")
        
    hidden = d.get('raw_tool_names_hidden_from_answer')
    if not hidden:
        print(f"  FAIL: raw_tool_names_hidden_from_answer = {hidden}")
        all_pass = False
        
    forbidden = d.get('forbidden_patterns_remaining_after_rewrite')
    if forbidden:
        print(f"  FAIL: forbidden_patterns_remaining_after_rewrite = {forbidden}")
        all_pass = False
        
    deployment = d.get('production_deployment')
    if deployment != "HOLD":
        print(f"  FAIL: production_deployment = {deployment} (expected HOLD)")
        all_pass = False

    raw_tools = ['chain_law_system', 'chain_procedure_detail', 'chain_ordinance_compare',
                 'chain_full_research', 'search_law', 'get_law_text', 'search_admin_rule', 'get_admin_rule']
    ans = d.get('answer', '')
    leaked = [t for t in raw_tools if t in ans]
    if leaked:
        print(f"  FAIL: Raw tool names leaked in answer: {leaked}")
        all_pass = False
        
    legal_conc = d.get('legal_conclusion_allowed')
    if legal_conc:
         print(f"  FAIL: legal_conclusion_allowed = {legal_conc}")
         all_pass = False
         
    contract_prom = d.get('contract_possible_auto_promoted')
    if contract_prom:
         print(f"  FAIL: contract_possible_auto_promoted = {contract_prom}")
         all_pass = False
         
    # Check specific scenario constraints
    if s == 'a':
        if d.get('tier_resolved') != 2: print("  FAIL: tier_resolved != 2"); all_pass = False
        if d.get('answer_schema_version') != "regional_procurement_v2": print("  FAIL: answer_schema_version != regional_procurement_v2"); all_pass = False
        if d.get('answer_builder_used') != "build_regional_procurement_answer": print("  FAIL: answer_builder_used != build_regional_procurement_answer"); all_pass = False
        if d.get('candidate_table_source') != "server_structured_formatter": print("  FAIL: candidate_table_source != server_structured_formatter"); all_pass = False
        if len(d.get('mandatory_mcp_executed', [])) < 6 and d.get('legal_basis_cache_hit_count', 0) < 6: print("  FAIL: Not enough MCP executed or cache hits"); all_pass = False
        if d.get('mandatory_mcp_missing'): print("  FAIL: mandatory_mcp_missing not empty"); all_pass = False
        if not d.get('legal_basis_table_rendered'): print("  FAIL: legal_basis_table_rendered != true"); all_pass = False
        if d.get('rag_elapsed_ms') != 0: print("  FAIL: rag_elapsed_ms != 0"); all_pass = False
        if d.get('model_elapsed_ms') != 0: print("  FAIL: model_elapsed_ms != 0"); all_pass = False

    elif s == 'b':
        if d.get('tier_resolved') != 1: print("  FAIL: tier_resolved != 1"); all_pass = False
        if d.get('answer_schema_version') != "amount_contract_guidance_v1": print("  FAIL: answer_schema_version != amount_contract_guidance_v1"); all_pass = False
        if d.get('answer_builder_used') != "build_amount_contract_guidance_answer": print("  FAIL: answer_builder_used != build_amount_contract_guidance_answer"); all_pass = False
        if d.get('candidate_table_source') != "none": print("  FAIL: candidate_table_source != none"); all_pass = False
        if len(d.get('mandatory_mcp_executed', [])) < 2 and d.get('legal_basis_cache_hit_count', 0) < 2: print("  FAIL: Not enough MCP executed or cache hits"); all_pass = False
        if d.get('mandatory_mcp_missing'): print("  FAIL: mandatory_mcp_missing not empty"); all_pass = False
        if not d.get('legal_basis_table_rendered'): print("  FAIL: legal_basis_table_rendered != true"); all_pass = False
        if d.get('rag_elapsed_ms') != 0: print("  FAIL: rag_elapsed_ms != 0"); all_pass = False
        if d.get('model_elapsed_ms') != 0: print("  FAIL: model_elapsed_ms != 0"); all_pass = False

    elif s == 'c':
        if d.get('tier_resolved') != 2: print("  FAIL: tier_resolved != 2"); all_pass = False
        if d.get('answer_schema_version') != "regional_procurement_v2": print("  FAIL: answer_schema_version != regional_procurement_v2"); all_pass = False
        if d.get('answer_builder_used') != "build_regional_procurement_answer": print("  FAIL: answer_builder_used != build_regional_procurement_answer"); all_pass = False
        if d.get('candidate_table_source') != "server_structured_formatter": print("  FAIL: candidate_table_source != server_structured_formatter"); all_pass = False
        if not d.get('legal_basis_cache_used'): print("  FAIL: legal_basis_cache_used != true"); all_pass = False
        if d.get('legal_basis_cache_hit_count', 0) < 6: print("  FAIL: legal_basis_cache_hit_count < 6"); all_pass = False
        if d.get('source_status') != "cached_verified": print("  FAIL: source_status != cached_verified"); all_pass = False
        if d.get('source_status_user_label') != "캐시된 확인 근거 사용": print("  FAIL: source_status_user_label != 캐시된 확인 근거 사용"); all_pass = False
        if "캐시된 확인 근거 사용" not in ans: print("  FAIL: Per-row cache status not in answer"); all_pass = False
        if "캐시로 재사용" not in ans: print("  FAIL: Cache notice not in answer"); all_pass = False
        if d.get('rag_elapsed_ms') != 0: print("  FAIL: rag_elapsed_ms != 0"); all_pass = False
        if d.get('model_elapsed_ms') != 0: print("  FAIL: model_elapsed_ms != 0"); all_pass = False

    elif s == 'd':
        if d.get('tier_resolved') != 0: print("  FAIL: tier_resolved != 0"); all_pass = False
        if d.get('answer_schema_version') != "simplified_company_search_v1": print("  FAIL: answer_schema_version != simplified_company_search_v1"); all_pass = False
        if d.get('answer_builder_used') != "build_simple_company_search_answer": print("  FAIL: answer_builder_used != build_simple_company_search_answer"); all_pass = False
        if d.get('candidate_table_source') != "server_structured_formatter": print("  FAIL: candidate_table_source != server_structured_formatter"); all_pass = False
        if d.get('legal_basis_table_rendered'): print("  FAIL: legal_basis_table_rendered != false"); all_pass = False
        if d.get('source_status') != "no_mcp_required": print("  FAIL: source_status != no_mcp_required"); all_pass = False
        if d.get('source_status_user_label') != "법령조회 불필요": print("  FAIL: source_status_user_label != 법령조회 불필요"); all_pass = False
        if d.get('mandatory_mcp_plan'): print("  FAIL: mandatory_mcp_plan not empty"); all_pass = False
        if d.get('mandatory_mcp_executed'): print("  FAIL: mandatory_mcp_executed not empty"); all_pass = False
        if d.get('mandatory_mcp_missing'): print("  FAIL: mandatory_mcp_missing not empty"); all_pass = False
        if d.get('model_selected') != "bypass_tier_0": print("  FAIL: model_selected != bypass_tier_0"); all_pass = False

    # Check Latency
    lat = d.get('latency_ms', 999999)
    limit = latency_limits[s]
    if lat > limit:
        print(f"  FAIL: latency_ms = {lat} > {limit}")
        all_pass = False
    else:
        print(f"  PASS: latency_ms = {lat} <= {limit}")


print("\n=== Latency Summary ===")
print("| Scenario | Tier | latency_ms | rag_elapsed_ms | model_elapsed_ms | rewrite_elapsed_ms | mcp_preflight_elapsed_ms | answer_builder_elapsed_ms | answer_builder_network_call_count | PASS/FAIL |")
print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
for s in scenarios:
    d = data[s]
    tier = d.get('tier_resolved', '-')
    lat = d.get('latency_ms', '-')
    rag = d.get('rag_elapsed_ms', '-')
    model = d.get('model_elapsed_ms', '-')
    rewrite = d.get('rewrite_elapsed_ms', '-')
    mcp = d.get('mcp_preflight_elapsed_ms', '-')
    ans_bld = d.get('answer_builder_elapsed_ms', '-')
    net = d.get('answer_builder_network_call_count', '-')
    pf = "PASS" if lat <= latency_limits[s] and net == 0 else "FAIL"
    print(f"| {s.upper()} | {tier} | {lat} | {rag} | {model} | {rewrite} | {mcp} | {ans_bld} | {net} | {pf} |")

if all_pass:
    print("\nOVERALL STATUS: PASS")
else:
    print("\nOVERALL STATUS: FAIL")

with open('latency_summary.md', 'w', encoding='utf-8') as f:
    f.write("=== Latency Summary ===\n")
    f.write("| Scenario | Tier | latency_ms | rag_elapsed_ms | model_elapsed_ms | rewrite_elapsed_ms | mcp_preflight_elapsed_ms | answer_builder_elapsed_ms | answer_builder_network_call_count | PASS/FAIL |\n")
    f.write("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|\n")
    for s in scenarios:
        d = data[s]
        tier = d.get('tier_resolved', '-')
        lat = d.get('latency_ms', '-')
        rag = d.get('rag_elapsed_ms', '-')
        model = d.get('model_elapsed_ms', '-')
        rewrite = d.get('rewrite_elapsed_ms', '-')
        mcp = d.get('mcp_preflight_elapsed_ms', '-')
        ans_bld = d.get('answer_builder_elapsed_ms', '-')
        net = d.get('answer_builder_network_call_count', '-')
        pf = "PASS" if lat <= latency_limits[s] and net == 0 else "FAIL"
        f.write(f"| {s.upper()} | {tier} | {lat} | {rag} | {model} | {rewrite} | {mcp} | {ans_bld} | {net} | {pf} |\n")
