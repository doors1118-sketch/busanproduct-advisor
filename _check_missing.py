import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

REQUIRED = [
    "tier_resolved", "answer_schema_version", "answer_builder_used",
    "answer_builder_elapsed_ms", "answer_builder_network_call_count",
    "latency_ms", "rag_elapsed_ms", "model_elapsed_ms",
    "rewrite_elapsed_ms", "mcp_preflight_elapsed_ms",
    "legal_basis_cache_used", "legal_basis_cache_hit_count",
    "legal_basis_cache_miss_count", "source_status", "source_status_user_label",
    "candidate_table_source", "candidate_counts_by_type",
    "mandatory_mcp_plan", "mandatory_mcp_executed", "mandatory_mcp_missing",
    "forbidden_patterns_remaining_after_rewrite",
    "legal_conclusion_allowed", "contract_possible_auto_promoted",
    "production_deployment",
]

for s in ['a','b','c','d']:
    d = json.load(open(f'scenario_{s}_raw.json', encoding='utf-8-sig'))
    missing = [f for f in REQUIRED if f not in d or d[f] is None]
    print(f'{s.upper()}: missing={missing}')
