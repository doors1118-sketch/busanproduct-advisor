"""
TC7 tool_result staging integration 검증
- 실제 search_innovation_products / search_tech_development_products를 tool_result 형태로 호출
- classify_candidates → format_candidate_tables 경로 검증
- 금지 표현(forbidden_patterns) 검출
- 민감정보 미노출 검증
- Gemini runtime test가 아니라 tool_result staging integration test
"""
import sys, os, json, re
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from policies.candidate_policy import (
    classify_candidates, get_candidate_counts, normalize_candidates,
    build_required_checks, get_data_source_status, CANDIDATE_TYPES,
)
from policies.candidate_formatter import format_candidate_tables

# ─────────────────────────────────────────────
# 금지 표현 목록
# ─────────────────────────────────────────────
FORBIDDEN_PATTERNS = [
    r"금액\s*제한\s*없이\s*수의계약\s*가능",
    r"금액\s*무제한\s*수의계약",
    r"수의계약\s*가능합니다",
    r"수의계약이\s*가능합니다",
    r"바로\s*수의계약",
    r"계약\s*체결이?\s*가능합니다",
]


def _check_forbidden(text: str) -> list:
    matched = []
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, text):
            matched.append(pat)
    return matched


def _check_sensitive(rows: list) -> list:
    detected = []
    for row in rows:
        if "biz_no" in row:
            detected.append("biz_no_field_present")
        if "representative" in row:
            detected.append("representative_field_present")
        row_str = json.dumps(row, ensure_ascii=False)
        if re.search(r"\d{3}-\d{2}-\d{5}", row_str):
            detected.append("사업자등록번호_하이픈형")
    return detected


def _simulate_tool_call(tool_name: str, query: str) -> dict:
    """실제 검색 함수를 호출하고 gemini_engine._execute_function_call과 동일한 JSON 구조 반환"""
    if tool_name == "search_innovation_products":
        from policies.innovation_search import search_innovation_products
        result = search_innovation_products(query, n_results=10)
        return {
            "tool_name": tool_name,
            "status": "success",
            "structured_rows": result.get("product_sample_rows", []),
            "product_sample_rows": result.get("product_sample_rows", []),
            "innovation_product_count": result.get("innovation_product_count", 0),
            "product_name_matched_count": result.get("product_name_matched_count", 0),
            "low_confidence_count": result.get("low_confidence_count", 0),
            "unknown_cert_count": result.get("unknown_cert_count", 0),
            "data_source_status": result.get("data_source_status", "connected_local_search"),
            "runtime_tool_integration": "connected_staging",
            "sensitive_fields_removed": True,
            "contract_possible_auto_promoted": False,
        }
    elif tool_name == "search_tech_development_products":
        from policies.innovation_search import search_tech_development_products
        result = search_tech_development_products(query, max_results=10)
        return {
            "tool_name": tool_name,
            "status": "success",
            "structured_rows": result.get("product_sample_rows", []),
            "product_sample_rows": result.get("product_sample_rows", []),
            "priority_purchase_count": result.get("priority_purchase_count", 0),
            "matched_business_no_count": result.get("matched_business_no_count", 0),
            "unmatched_tech_product_count": result.get("unmatched_tech_product_count", 0),
            "unmatched_count_scope": "search_result_vs_busan_procurement_db",
            "matched_count_scope": "tech_products.json 전체 중 부산 조달업체 DB 사업자번호 매칭",
            "total_source_product_count": result.get("total_source_product_count", 0),
            "valid_cert_count": result.get("valid_cert_count", 0),
            "expired_cert_count": result.get("expired_cert_count", 0),
            "unknown_cert_count": result.get("unknown_cert_count", 0),
            "data_source_status": result.get("data_source_status", "connected_local_search"),
            "runtime_tool_integration": "connected_staging",
            "sensitive_fields_removed": True,
            "contract_possible_auto_promoted": False,
        }
    return {"tool_name": tool_name, "status": "error", "error": "unknown tool"}


# ─────────────────────────────────────────────
# 검증 케이스 정의
# ─────────────────────────────────────────────
TEST_CASES = [
    {
        "test_case": "RT-1_Innovation_Product_Search",
        "query": "공기청정기 혁신제품 부산업체 찾아줘",
        "tool_name": "search_innovation_products",
        "tool_query": "공기청정기",
    },
    {
        "test_case": "RT-2_Innovation_Prototype_Search",
        "query": "배전반 혁신시제품 찾아줘",
        "tool_name": "search_innovation_products",
        "tool_query": "배전반",
    },
    {
        "test_case": "RT-3_Tech_Dev_Product_Search",
        "query": "부산업체 중 기술개발제품 인증 보유 LED 업체 찾아줘",
        "tool_name": "search_tech_development_products",
        "tool_query": "LED",
    },
    {
        "test_case": "RT-4_Forbidden_Expression_Check",
        "query": "혁신제품이면 금액 제한 없이 수의계약 가능해?",
        "tool_name": "search_innovation_products",
        "tool_query": "혁신제품",
    },
]


# ─────────────────────────────────────────────
# 고위험 질문 판별
# ─────────────────────────────────────────────
LEGAL_JUDGMENT_KEYWORDS = [
    "가능해", "가능한가", "가능합니까", "되나요", "되는지", "할 수 있",
    "수의계약 가능", "금액 제한 없이", "무제한",
]

BLOCKED_SCOPE_MAP = {
    "금액": "amount_threshold",
    "제한 없이": "amount_threshold",
    "무제한": "amount_threshold",
    "혁신제품": "innovation_product_special_rule",
    "혁신시제품": "innovation_product_special_rule",
}


def _detect_legal_judgment(query: str) -> dict:
    """고위험 법적 판단 요청 감지"""
    q_lower = query.lower()
    requested = any(kw in q_lower for kw in LEGAL_JUDGMENT_KEYWORDS)
    blocked_scope = []
    for kw, scope in BLOCKED_SCOPE_MAP.items():
        if kw in q_lower and scope not in blocked_scope:
            blocked_scope.append(scope)
    return {
        "legal_judgment_requested": requested,
        "legal_judgment_allowed": False,
        "legal_conclusion_allowed": False,
        "blocked_scope": blocked_scope if requested else [],
        "company_table_allowed": True,
    }


def run_runtime_test(tc: dict) -> dict:
    """단일 tool_result staging integration 검증 케이스 실행"""
    test_case = tc["test_case"]
    query = tc["query"]
    tool_name = tc["tool_name"]
    tool_query = tc["tool_query"]

    # 1. tool 호출
    tool_result = _simulate_tool_call(tool_name, tool_query)
    tool_called = tool_result.get("status") == "success"

    # 2. classify_candidates 통과
    tool_results_for_classify = [{
        "tool_name": tool_name,
        "status": "success",
        "result": json.dumps(tool_result, ensure_ascii=False),
        **tool_result,
    }]
    classified = classify_candidates(tool_results_for_classify, query)

    # 3. format_candidate_tables 통과
    formatted = format_candidate_tables(classified, query, "", is_staging=True)

    # 4. 결과 집계
    rows = []
    candidate_types = []
    primary_candidate_type = ""
    purchase_routes = []
    innovation_count = 0
    priority_count = 0
    matched_biz = "not_applicable"
    unmatched_tech = "not_applicable"
    unmatched_scope = "not_applicable"
    matched_count_scope = "not_applicable"
    total_source_product_count = "not_applicable"

    if "innovation" in tool_name:
        rows = classified.get("innovation_product", [])
        innovation_count = len(rows)
        candidate_types = ["innovation_product"]
        primary_candidate_type = "innovation_product"
        purchase_routes = CANDIDATE_TYPES["innovation_product"]["purchase_routes"]
    elif "tech_development" in tool_name:
        rows = classified.get("priority_purchase_product", [])
        priority_count = len(rows)
        matched_biz = tool_result.get("matched_business_no_count", 0)
        unmatched_tech = tool_result.get("unmatched_tech_product_count", 0)
        unmatched_scope = tool_result.get("unmatched_count_scope", "")
        matched_count_scope = tool_result.get("matched_count_scope", "")
        total_source_product_count = tool_result.get("total_source_product_count", 0)
        candidate_types = ["priority_purchase_product"]
        primary_candidate_type = "priority_purchase_product"
        purchase_routes = CANDIDATE_TYPES["priority_purchase_product"]["purchase_routes"]

    # 5. 민감정보 검증
    sensitive_detected = _check_sensitive(rows)

    # 6. 금지 표현 검증
    forbidden_matched = _check_forbidden(formatted)

    # 7. contract_possible_auto_promoted 전 행 검증
    auto_ok = all(r.get("contract_possible_auto_promoted") is False for r in rows)

    # 8. 표 생성 여부
    staging_table_generated = len(formatted.strip()) > 0
    production_table_generated = False  # production_display_enabled=false 이므로 항상 false

    # 9. 고위험 법적 판단 감지
    legal_info = _detect_legal_judgment(query)

    # 10. PASS 판정
    passed = (
        tool_called
        and len(rows) > 0
        and auto_ok
        and len(sensitive_detected) == 0
        and len(forbidden_matched) == 0
    )

    ds = get_data_source_status(primary_candidate_type)

    matched_in_returned = "not_applicable"
    if "tech_development" in tool_name:
        matched_in_returned = sum(
            1 for r in rows if r.get("certification_no") or r.get("match_basis")
        )

    result = {
        "test_case": test_case,
        "test_type": "tool_result_staging_integration",
        "query": query,
        "tool_called": tool_called,
        "tool_name": tool_name,
        "runtime_tool_integration": "connected_staging",
        "data_source_status": ds["data_source_status"],
        "model_selected": "N/A (tool_result staging — Gemini runtime bypass)",
        "model_used": "N/A (local_search_direct)",
        "candidate_types": candidate_types,
        "primary_candidate_type": primary_candidate_type,
        "purchase_routes": purchase_routes,
        "product_sample_rows": rows[:3],
        "returned_row_count": len(rows),
        "priority_purchase_count": priority_count,
        "innovation_product_count": innovation_count,
        "matched_business_no_count": matched_biz,
        "matched_business_no_count_in_returned_rows": matched_in_returned,
        "matched_count_scope": matched_count_scope,
        "total_source_product_count": total_source_product_count,
        "unmatched_tech_product_count": unmatched_tech,
        "unmatched_count_scope": unmatched_scope,
        "sensitive_fields_removed": True,
        "sensitive_fields_detected": sensitive_detected,
        "contract_possible_auto_promoted": False,
        "forbidden_patterns_matched": forbidden_matched,
        "staging_table_generated": staging_table_generated,
        "production_table_generated": production_table_generated,
        "staging_display_only": ds.get("staging_display_only", True),
        "production_display_enabled": ds.get("production_display_enabled", False),
        **legal_info,
        "final_answer_preview": formatted[:600] if formatted else "(표 미생성 — display_enabled=false)",
        "pass": passed,
        "failure_reason": "" if passed else (
            f"tool_called={tool_called}, rows={len(rows)}, auto_ok={auto_ok}, "
            f"sensitive={sensitive_detected}, forbidden={forbidden_matched}"
        ),
    }
    return result


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
if __name__ == "__main__":
    results = []
    for tc in TEST_CASES:
        print(f"  Running {tc['test_case']}...")
        r = run_runtime_test(tc)
        results.append(r)

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tc7_runtime_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {out_path}")

    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"  [{status}] {r['test_case']}: {r.get('failure_reason', '')}")

    # 보고서
    md = "# TC7 tool_result staging integration 검증 보고서\n\n"
    all_pass = all(r["pass"] for r in results)
    md += "## Status\n"
    md += f"- **Tool result staging integration**: {'PASS' if all_pass else 'PARTIAL_PASS'}\n"
    md += "- **Gemini runtime test**: NOT_RUN (다음 단계)\n"
    md += "- **Production deployment**: HOLD\n\n"

    md += "## Raw JSON Output\n\n"
    for r in results:
        md += f"### {r['test_case']}\n"
        md += "```json\n"
        md += json.dumps(r, ensure_ascii=False, indent=2)
        md += "\n```\n\n"

    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TC7_runtime_result.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved to: {report_path}")
