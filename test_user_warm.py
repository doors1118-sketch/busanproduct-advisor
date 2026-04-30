import requests
import json
from pathlib import Path

URL = "http://127.0.0.1:8001/chat"
q = "7천만원으로 컴퓨터 구매해야 한다. 가급적 지역업체랑 계약하고 싶은데 방법이 있을까?"

def run_once(idx: int):
    res = requests.post(URL, json={"message": q}, timeout=120)
    res.raise_for_status()
    data = res.json()

    Path(f"scenario_a_warm_run_{idx}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    checks = {
        "tier_resolved=2": data.get("tier_resolved") == 2,
        "answer_schema_version=regional_procurement_v2": data.get("answer_schema_version") == "regional_procurement_v2",
        "candidate_table_source=server_structured_formatter": data.get("candidate_table_source") == "server_structured_formatter",
        "mandatory_mcp_executed>=6": len(data.get("mandatory_mcp_executed", [])) >= 6,
        "mandatory_mcp_missing=[]": data.get("mandatory_mcp_missing") == [],
        "legal_conclusion_allowed=false": data.get("legal_conclusion_allowed") is False,
        "contract_possible_auto_promoted=false": data.get("contract_possible_auto_promoted") is False,
        "forbidden_patterns_remaining_after_rewrite=[]": data.get("forbidden_patterns_remaining_after_rewrite") == [],
        "production_deployment=HOLD": data.get("production_deployment") == "HOLD",
        "latency<=45000": (data.get("total_latency_ms") or data.get("latency_ms") or 999999) <= 45000,
        "rag_elapsed_ms=0": data.get("rag_elapsed_ms") in (0, None),
        "cache_hit_count>=6": data.get("legal_basis_cache_hit_count", 0) >= 6,
    }

    print(f"\nRun {idx}")
    print(f"latency={data.get('total_latency_ms') or data.get('latency_ms')}ms")
    print(f"rag={data.get('rag_elapsed_ms')}ms")
    print(f"cache_hits={data.get('legal_basis_cache_hit_count')}")
    print(f"mcp_executed={len(data.get('mandatory_mcp_executed', []))}")
    print(f"production={data.get('production_deployment')}")
    for name, ok in checks.items():
        print(("PASS " if ok else "FAIL ") + name)

    return all(checks.values()), data

ok1, data1 = run_once(1)
ok2, data2 = run_once(2)

summary = {
    "run1_pass": ok1,
    "run2_pass": ok2,
    "run1_latency_ms": data1.get("total_latency_ms") or data1.get("latency_ms"),
    "run2_latency_ms": data2.get("total_latency_ms") or data2.get("latency_ms"),
    "run1_cache_hits": data1.get("legal_basis_cache_hit_count"),
    "run2_cache_hits": data2.get("legal_basis_cache_hit_count"),
    "production_deployment": data2.get("production_deployment"),
}

Path("warm_cache_test_summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("\nSUMMARY")
print(json.dumps(summary, ensure_ascii=False, indent=2))

if not (ok1 and ok2):
    raise SystemExit(1)
