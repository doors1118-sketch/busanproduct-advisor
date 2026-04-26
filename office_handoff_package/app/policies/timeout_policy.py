"""
MCP Timeout Policy — wrapper + HTTP client timeout 이중 적용
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from prompting.schemas import LegalConclusionScope

# ─── 환경변수 기반 timeout (초) ───
MCP_TIMEOUT_MAP = {
    "chain_full_research":    int(os.getenv("MCP_CHAIN_TIMEOUT_SECONDS", "12")),
    "chain_law_system":       int(os.getenv("MCP_CHAIN_TIMEOUT_SECONDS", "12")),
    "chain_procedure_detail": int(os.getenv("MCP_CHAIN_TIMEOUT_SECONDS", "12")),
    "chain_ordinance_compare":int(os.getenv("MCP_CHAIN_TIMEOUT_SECONDS", "12")),
    "chain_amendment_track":  int(os.getenv("MCP_CHAIN_TIMEOUT_SECONDS", "12")),
    "chain_document_review":  int(os.getenv("MCP_CHAIN_TIMEOUT_SECONDS", "12")),
    "chain_action_basis":     int(os.getenv("MCP_CHAIN_TIMEOUT_SECONDS", "12")),
    "get_law_text":           int(os.getenv("MCP_LAW_TEXT_TIMEOUT_SECONDS", "10")),
    "search_law":             int(os.getenv("MCP_LAW_TEXT_TIMEOUT_SECONDS", "10")),
    "search_admin_rule":      int(os.getenv("MCP_ADMIN_RULE_TIMEOUT_SECONDS", "10")),
    "get_admin_rule":         int(os.getenv("MCP_ADMIN_RULE_TIMEOUT_SECONDS", "10")),
    "search_decisions":       int(os.getenv("MCP_DECISION_TIMEOUT_SECONDS", "5")),
    "search_interpretations": int(os.getenv("MCP_DECISION_TIMEOUT_SECONDS", "5")),
    "get_decision_text":      int(os.getenv("MCP_DECISION_TIMEOUT_SECONDS", "5")),
    "get_annexes":            int(os.getenv("MCP_ORDINANCE_TIMEOUT_SECONDS", "8")),
    "verify_citations":       int(os.getenv("MCP_LAW_TEXT_TIMEOUT_SECONDS", "10")),
}

DEFAULT_TIMEOUT = 10

# ─── 핵심 법령 도구 (fail-closed 대상) ───
CRITICAL_LAW_TOOLS = {
    "get_law_text", "search_law", "chain_law_system",
    "chain_full_research", "get_annexes",
}

# 금액 판단 필수 도구
AMOUNT_THRESHOLD_TOOLS = {
    "get_law_text", "search_law", "chain_law_system",
    "chain_full_research", "get_annexes",
    "search_admin_rule", "get_admin_rule",
}


def get_timeout(tool_name: str) -> int:
    """도구별 timeout 반환"""
    return MCP_TIMEOUT_MAP.get(tool_name, DEFAULT_TIMEOUT)


def call_mcp_with_timeout(func, tool_name: str, **kwargs) -> dict:
    """
    MCP 도구 호출 + timeout 래퍼.
    wrapper timeout으로 제어하며, HTTP client timeout은 mcp_client.py에서 적용.
    
    Returns: {"status": "success|timeout|failed", "result": str, "elapsed_ms": int}
    """
    timeout_sec = get_timeout(tool_name)
    start = time.time()

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(func, **kwargs)
            result = future.result(timeout=timeout_sec)
            elapsed = int((time.time() - start) * 1000)
            return {
                "status": "success",
                "result": result,
                "elapsed_ms": elapsed,
                "tool_name": tool_name,
            }
    except FuturesTimeoutError:
        elapsed = int((time.time() - start) * 1000)
        print(f"  [TIMEOUT] {tool_name} exceeded {timeout_sec}s ({elapsed}ms)")
        return {
            "status": "timeout",
            "result": f"[TIMEOUT] {tool_name}: {timeout_sec}초 초과",
            "elapsed_ms": elapsed,
            "tool_name": tool_name,
        }
    except Exception as e:
        elapsed = int((time.time() - start) * 1000)
        print(f"  [FAILED] {tool_name}: {e}")
        return {
            "status": "failed",
            "result": f"[FAILED] {tool_name}: {str(e)}",
            "elapsed_ms": elapsed,
            "tool_name": tool_name,
        }


def evaluate_legal_scope(tool_results: list[dict]) -> LegalConclusionScope:
    """
    MCP 호출 결과 목록을 분석하여 법적 결론 범위를 결정.
    승인 조건 4번: blocked_scope가 최종 답변 생성을 실제 제어.
    """
    allowed = []
    blocked = []
    critical = []

    has_core_law = False
    has_admin_rule = False
    has_precedent = False
    has_ordinance = False

    for r in tool_results:
        name = r.get("tool_name", "")
        status = r.get("status", "failed")

        if status == "success":
            if name in CRITICAL_LAW_TOOLS:
                has_core_law = True
            if name in ("search_admin_rule", "get_admin_rule"):
                has_admin_rule = True
            if name in ("search_decisions", "search_interpretations", "get_decision_text"):
                has_precedent = True
        else:
            if name in CRITICAL_LAW_TOOLS:
                if status == "skipped":
                    critical.append(f"broad_query_skip_{name}")
                    blocked.append("amount_threshold")
                    blocked.append("one_person_quote")
                    blocked.append("broad_query_scope")
                else:
                    critical.append(f"{name}_{status}")
                    blocked.append("amount_threshold")
                    blocked.append("one_person_quote")
                    blocked.append("api_timeout")
            if name in ("search_admin_rule", "get_admin_rule"):
                critical.append(f"admin_rule_{status}")
                blocked.append("amount_threshold")
            if name in ("search_decisions", "search_interpretations"):
                # 판례/해석례 timeout은 법령 판단 자체를 막지 않음
                pass

    # 답변 가능 범위 결정
    if has_core_law:
        allowed.append("central_law_summary")
    allowed.append("general_procedure")

    if has_precedent:
        allowed.append("precedent_reference")

    if has_admin_rule:
        allowed.append("admin_rule_detail")

    # blocked 중복 제거
    blocked = sorted(set(blocked))
    critical = sorted(set(critical))

    conclusion_allowed = len(critical) == 0

    return LegalConclusionScope(
        legal_conclusion_allowed=conclusion_allowed,
        allowed_scope=allowed,
        blocked_scope=blocked,
        critical_missing=critical,
    )
