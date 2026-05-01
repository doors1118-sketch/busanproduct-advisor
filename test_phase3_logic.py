import sys, os, time, json, urllib.request
sys.path.append(os.path.abspath('app'))

# --- 1. is_mcp_error 테스트 ---
from app.gemini_engine import is_mcp_error

test_inputs = [
    (None, True),
    ("", True),
    ("MCP 호출 오류: Read timed out", True),
    ('{"warning":"외부 API 응답 지연"}', True),
    ('{"error":"API 오류"}', True),
    ('{"success": false}', True),
    ('{"status": "timeout"}', True),
    ("[TIMEOUT] chain_full_research", True),
    ("Max retries exceeded with url", True),
    ("정상 법령 검색 결과", False),
]

print("--- 1. is_mcp_error 테스트 ---")
for inp, expected in test_inputs:
    actual = is_mcp_error(inp)
    print(f"Input: {inp!r} | Expected: {expected} | Actual: {actual} | PASS: {actual == expected}")


# --- 2. cache safety 테스트 ---
print("\n--- 2. cache safety 테스트 ---")
from app.gemini_engine import _execute_tier_2_mandatory_mcp, _mcp_cache

# Mock execution to return an error
def _execute_function_call_mock(fc):
    return '{"status": "timeout"}'

import app.gemini_engine
app.gemini_engine._execute_function_call = _execute_function_call_mock

_mcp_cache.clear()
plan = [{"name": "search_law", "args": {"query": "수의계약"}}]

mcp_context, _, executed, missing, cache_stats = _execute_tier_2_mandatory_mcp("test", plan)

print(f"_mcp_cache len: {len(_mcp_cache)} | PASS: {len(_mcp_cache) == 0}")
print(f"executed len: {len(executed)} | PASS: {len(executed) == 0}")
print(f"missing len: {len(missing)} | PASS: {len(missing) == 1}")
print(f"context text contains placeholder: {'[MCP_FAILED]' in mcp_context} | PASS: {'[MCP_FAILED]' in mcp_context}")
print(f"context text contains json error: {'timeout' in mcp_context} | PASS: {'timeout' not in mcp_context}")


# --- 3. source_status 분기 테스트 ---
print("\n--- 3. source_status 분기 테스트 ---")
def get_source_status(tier, executed_len, missing_len, hits, called_for_miss):
    meta = {
        "tier_resolved": tier,
        "mandatory_mcp_executed": ["x"] * executed_len,
        "mandatory_mcp_missing": ["x"] * missing_len,
        "legal_basis_cache_hit_count": hits,
        "mcp_called_for_cache_miss": called_for_miss
    }
    _pre_mcp = meta.get("mandatory_mcp_executed", [])
    _pre_missing = meta.get("mandatory_mcp_missing", [])
    _pre_tier = meta.get("tier_resolved", 1)
    _pre_hits = meta.get("legal_basis_cache_hit_count", 0)
    
    if _pre_tier == 0:
        return "no_mcp_required"
    elif _pre_missing and _pre_mcp:
        return "partial_mcp_with_missing"
    elif _pre_missing and _pre_hits > 0:
        return "cached_stale_but_available"
    elif _pre_missing and not _pre_mcp and _pre_hits == 0:
        return "mcp_failed_no_basis"
    elif _pre_hits > 0 and not _pre_missing:
        return "cached_verified"
    elif _pre_mcp and meta.get("mcp_called_for_cache_miss"):
        return "cache_refreshed_from_mcp"
    elif _pre_mcp:
        return "mcp_preflight_success"
    else:
        return "mcp_failed_no_basis"

cases = [
    (0, 0, 0, 0, False, "no_mcp_required"),
    (1, 1, 1, 0, False, "partial_mcp_with_missing"),
    (1, 0, 1, 1, False, "cached_stale_but_available"),
    (1, 0, 1, 0, False, "mcp_failed_no_basis"),
    (1, 0, 0, 1, False, "cached_verified"),
    (1, 1, 0, 0, True, "cache_refreshed_from_mcp"),
    (1, 1, 0, 0, False, "mcp_preflight_success"),
]
for t, e, m, h, c, exp in cases:
    act = get_source_status(t, e, m, h, c)
    print(f"Case(t={t}, e={e}, m={m}, h={h}, c={c}) | Exp: {exp} | Act: {act} | PASS: {act == exp}")

