"""
TC7 후보군 분류체계 5종 확장 검증 스크립트 v2
- TC7-1: 종합쇼핑몰 등록 부산업체 후보
- TC7-2: 조달등록 부산업체 후보
- TC7-3: 정책기업 후보
- TC7-4: 혁신제품·혁신시제품 후보
- TC7-5: 우선구매·특례제품 data_source_status 확인
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))

from policies.candidate_policy import (
    classify_candidates, classify_candidate_types, get_candidate_counts,
    normalize_candidates, split_policy_companies, build_required_checks,
    get_data_source_status, CANDIDATE_TYPES
)
from policies.candidate_formatter import format_candidate_tables, group_candidates_by_route


def _base_result(counts):
    """공통 카운터 필드"""
    return {
        "local_company_count": counts["local_company_count"],
        "mall_company_count": counts["mall_company_count"],
        "primary_policy_company_count": counts["primary_policy_company_count"],
        "tagged_policy_company_count": counts["tagged_policy_company_count"],
        "innovation_product_count": counts["innovation_product_count"],
        "priority_purchase_count": counts["priority_purchase_count"],
    }


# ── TC7-1: 종합쇼핑몰 등록 부산업체 후보 ──
def run_tc7_1():
    tool_results = [{
        "tool_name": "search_shopping_mall",
        "status": "success",
        "result": (
            "종합쇼핑몰 검색 결과: 총 2건\n\n"
            "1. (주)부산조명기업 (부산광역시 사상구) -- LED등기구\n"
            "2. (주)부산전자 (부산광역시 해운대구) -- CCTV카메라 <여성기업>"
        )
    }]
    classified = classify_candidates(tool_results, "종합쇼핑몰에서 LED 살 수 있어?")
    counts = get_candidate_counts(classified)
    ds = get_data_source_status("shopping_mall_supplier")
    all_rows = normalize_candidates(classified.get("shopping_mall_supplier", []))
    auto_ok = all(r.get("contract_possible_auto_promoted") is False for r in all_rows)

    passed = counts["mall_company_count"] > 0 and auto_ok
    return {
        "test_case": "TC7-1_Shopping_Mall_Supplier",
        "description": "종합쇼핑몰 등록 부산업체 후보",
        "candidate_types_tested": ["shopping_mall_supplier"],
        "primary_candidate_type": "shopping_mall_supplier",
        "purchase_routes": CANDIDATE_TYPES["shopping_mall_supplier"]["purchase_routes"],
        "source_label": CANDIDATE_TYPES["shopping_mall_supplier"]["source_label"],
        "company_sample_rows": all_rows,
        **_base_result(counts),
        "contract_possible_auto_promoted": False,
        "all_candidates_auto_promoted_false": auto_ok,
        "legal_eligibility_status": "확인 필요",
        "required_checks": build_required_checks("shopping_mall_supplier"),
        "data_source_status": ds["data_source_status"],
        "data_source": ds["data_source"],
        "display_enabled": ds["display_enabled"],
        "final_answer_preview": format_candidate_tables(classified, "종합쇼핑몰에서 LED 살 수 있어?", "")[:500],
        "pass": passed,
        "failure_reason": "" if passed else "mall_company_count=0 또는 auto_promoted 위반"
    }


# ── TC7-2: 조달등록 부산업체 후보 ──
def run_tc7_2():
    tool_results = [{
        "tool_name": "search_local_company_by_product",
        "status": "success",
        "result": (
            "부산 지역업체 검색 결과: 총 3건 (상위 3건 표시)\n\n"
            "1. (주)선진텔레콤 (부산광역시 사상구) -- CCTV카메라 [계속사업자] [candidate]\n"
            "2. (주)유니원 (부산광역시 해운대구) -- CCTV카메라 [계속사업자] [candidate]\n"
            "3. 주식회사 태인테크 (부산광역시 부산진구) -- CCTV카메라 [계속사업자] [candidate]"
        )
    }]
    classified = classify_candidates(tool_results, "CCTV 부산 업체 추천해줘")
    counts = get_candidate_counts(classified)
    ds = get_data_source_status("local_procurement_company")
    all_rows = normalize_candidates(classified.get("local_procurement_company", []))
    auto_ok = all(r.get("contract_possible_auto_promoted") is False for r in all_rows)

    passed = counts["local_company_count"] > 0 and auto_ok
    return {
        "test_case": "TC7-2_Local_Procurement_Company",
        "description": "입찰·수의계약 검토용 조달등록 부산업체 후보",
        "candidate_types_tested": ["local_procurement_company"],
        "primary_candidate_type": "local_procurement_company",
        "purchase_routes": CANDIDATE_TYPES["local_procurement_company"]["purchase_routes"],
        "source_label": CANDIDATE_TYPES["local_procurement_company"]["source_label"],
        "company_sample_rows": all_rows,
        **_base_result(counts),
        "contract_possible_auto_promoted": False,
        "all_candidates_auto_promoted_false": auto_ok,
        "legal_eligibility_status": "확인 필요",
        "required_checks": build_required_checks("local_procurement_company"),
        "data_source_status": ds["data_source_status"],
        "data_source": ds["data_source"],
        "display_enabled": ds["display_enabled"],
        "final_answer_preview": format_candidate_tables(classified, "CCTV 부산 업체 추천해줘", "")[:500],
        "pass": passed,
        "failure_reason": "" if passed else "local_company_count=0 또는 auto_promoted 위반"
    }


# ── TC7-3: 정책기업 후보 ──
def run_tc7_3():
    tool_results = [{
        "tool_name": "search_local_company_by_product",
        "status": "success",
        "result": (
            "부산 지역업체 검색 결과: 총 4건 (상위 4건 표시)\n\n"
            "1. (주)모의여성기업 (부산광역시 남구) -- CCTV카메라 <여성기업> [계속사업자] [candidate]\n"
            "2. (주)장애인기업A (부산광역시 사상구) -- CCTV카메라 <장애인기업> [계속사업자] [candidate]\n"
            "3. (주)일반기업B (부산광역시 해운대구) -- CCTV카메라 [계속사업자] [candidate]\n"
            "4. (주)사회적기업C (부산광역시 연제구) -- CCTV카메라 <사회적기업> [계속사업자] [candidate]"
        )
    }]
    classified = classify_candidates(tool_results, "여성기업 CCTV 업체 추천해줘")
    counts = get_candidate_counts(classified)
    ds = get_data_source_status("policy_company")
    policy_rows = classified.get("policy_company", [])
    local_rows = classified.get("local_procurement_company", [])
    all_rows = normalize_candidates(policy_rows + local_rows)
    auto_ok = all(r.get("contract_possible_auto_promoted") is False for r in all_rows)

    # split_policy_companies 검증: 4건 입력, 3건 정책기업 분리 기대
    test_input = [
        {"policy_tags": ["여성기업"], "company_name": "A"},
        {"policy_tags": ["장애인기업"], "company_name": "B"},
        {"policy_tags": [], "company_name": "C"},
        {"policy_tags": ["사회적기업"], "company_name": "D"},
    ]
    pure, split = split_policy_companies(test_input)
    split_msg = f"split_policy_companies: 입력 {len(test_input)}건 → 정책기업 {len(split)}건, 일반 {len(pure)}건"

    passed = counts["primary_policy_company_count"] > 0 and auto_ok
    return {
        "test_case": "TC7-3_Policy_Company",
        "description": "정책기업 수의계약 검토 후보",
        "candidate_types_tested": ["policy_company", "local_procurement_company"],
        "primary_candidate_type": "policy_company",
        "purchase_routes": CANDIDATE_TYPES["policy_company"]["purchase_routes"],
        "source_label": CANDIDATE_TYPES["policy_company"]["source_label"],
        "company_sample_rows": policy_rows,
        **_base_result(counts),
        "contract_possible_auto_promoted": False,
        "all_candidates_auto_promoted_false": auto_ok,
        "legal_eligibility_status": "확인 필요",
        "required_checks": build_required_checks("policy_company"),
        "data_source_status": ds["data_source_status"],
        "data_source": ds["data_source"],
        "display_enabled": ds["display_enabled"],
        "split_policy_test": split_msg,
        "caution_text_present": CANDIDATE_TYPES["policy_company"].get("caution_text", "") != "",
        "final_answer_preview": format_candidate_tables(classified, "여성기업 CCTV 업체 추천해줘", "")[:600],
        "pass": passed,
        "failure_reason": "" if passed else "primary_policy_company_count=0 또는 auto_promoted 위반"
    }


# ── TC7-4: 혁신제품·혁신시제품 후보 ──
def run_tc7_4():
    ds = get_data_source_status("innovation_product")
    tool_results = [{
        "tool_name": "search_innovation_products",
        "status": "success",
        "result": (
            "[혁신제품 검색 결과]\n"
            "- 스마트 공기청정기 (모델: APC-3000)\n"
            "  업체: (주)부산클린테크 | 소재지: 부산광역시 강서구\n"
            "  구분: 유형1 | 인증번호: 2025-421 | 희망가격: 3,500,000원\n"
            "- IoT 배전반 (모델: SDB-100)\n"
            "  업체: (주)부산전력기기 | 소재지: 부산광역시 사상구\n"
            "  구분: 유형2 | 인증번호: 2024-112 | 희망가격: 12,000,000원"
        )
    }]
    classified = classify_candidates(tool_results, "혁신제품으로 등록된 부산 업체 추천해줘")
    counts = get_candidate_counts(classified)
    innov_rows = normalize_candidates(classified.get("innovation_product", []))
    auto_ok = all(r.get("contract_possible_auto_promoted") is False for r in innov_rows)

    schema_pass = auto_ok and ds["data_source_status"] == "schema_ready_search_pending" and ds["display_enabled"] is False

    # display_enabled=false이므로 운영 표 미출력 확인
    formatted = format_candidate_tables(classified, "혁신제품으로 등록된 부산 업체 추천해줘", "")
    table_not_shown = (formatted == "")

    return {
        "test_case": "TC7-4_Innovation_Product",
        "description": "혁신제품·혁신시제품 수의계약 검토 후보 — 스키마/포맷터 통과 검증",
        "innovation_product_schema_formatter": "PASS" if auto_ok else "FAIL",
        "innovation_product_actual_search_integration": "NOT_RUN",
        "test_fixture_only": True,
        "mock_used": True,
        "candidate_types_tested": ["innovation_product"],
        "primary_candidate_type": "innovation_product",
        "purchase_routes": CANDIDATE_TYPES["innovation_product"]["purchase_routes"],
        "source_label": CANDIDATE_TYPES["innovation_product"]["source_label"],
        "product_sample_rows": innov_rows,
        **_base_result(counts),
        "contract_possible_auto_promoted": False,
        "all_candidates_auto_promoted_false": auto_ok,
        "legal_eligibility_status": "확인 필요",
        "required_checks": build_required_checks("innovation_product"),
        "data_source_status": ds["data_source_status"],
        "data_source": ds["data_source"],
        "display_enabled": ds["display_enabled"],
        "table_not_shown_in_production": table_not_shown,
        "caution_text_present": CANDIDATE_TYPES["innovation_product"].get("caution_text", "") != "",
        "final_answer_preview": "(표 미출력 — display_enabled=false, 실제 검색 연동 전 운영 노출 차단)" if table_not_shown else formatted[:600],
        "pass": schema_pass,
        "failure_reason": "" if schema_pass else "auto_promoted 위반 또는 data_source_status/display_enabled 불일치"
    }


# ── TC7-5: 우선구매·특례제품 data_source_status 확인 ──
def run_tc7_5():
    ds = get_data_source_status("priority_purchase_product")
    meta = CANDIDATE_TYPES["priority_purchase_product"]
    classified = {"priority_purchase_product": []}
    formatted = format_candidate_tables(classified, "중증장애인생산품 추천해줘", "")
    empty_ok = (formatted == "")

    passed = ds["data_source_status"] == "not_connected" and ds["display_enabled"] is False and empty_ok
    return {
        "test_case": "TC7-5_Priority_Purchase_Product",
        "description": "우선구매·특례제품 데이터 소스 미연결 상태 검증",
        "implementation_status": "데이터 소스 미확보, 스키마만 선언",
        "candidate_types_tested": ["priority_purchase_product"],
        "primary_candidate_type": "priority_purchase_product",
        "purchase_routes": meta["purchase_routes"],
        "source_label": meta["source_label"],
        "product_sample_rows": [],
        "local_company_count": 0,
        "mall_company_count": 0,
        "primary_policy_company_count": 0,
        "tagged_policy_company_count": 0,
        "innovation_product_count": 0,
        "priority_purchase_count": 0,
        "contract_possible_auto_promoted": False,
        "all_candidates_auto_promoted_false": True,
        "legal_eligibility_status": "확인 필요",
        "required_checks": build_required_checks("priority_purchase_product"),
        "data_source_status": ds["data_source_status"],
        "data_source": ds["data_source"],
        "display_enabled": ds["display_enabled"],
        "empty_table_not_shown": empty_ok,
        "final_answer_preview": "(표 미출력 — display_enabled=false, data_source_status=not_connected)",
        "pass": passed,
        "failure_reason": "" if passed else "display_enabled 또는 data_source_status 불일치"
    }


# ── Main ──
if __name__ == "__main__":
    results = [run_tc7_1(), run_tc7_2(), run_tc7_3(), run_tc7_4(), run_tc7_5()]

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tc7_expanded_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"TC7 expanded results saved to: {out_path}")

    for r in results:
        status = "PASS" if r["pass"] else "FAIL"
        print(f"  [{status}] {r['test_case']}: {r.get('failure_reason', '')}")

    # ── 보고서 생성 ──
    md = "# TC7 후보군 분류체계 5종 확장 검증 보고서\n\n"
    all_pass = all(r["pass"] for r in results)
    passed_list = [r["test_case"] for r in results if r["pass"]]
    failed_list = [r["test_case"] for r in results if not r["pass"]]

    if all_pass:
        status_str = "PASS (All TC7 cases passed.)"
    elif passed_list:
        status_str = f"PARTIAL_PASS (Passed: {', '.join(passed_list)}. Failed: {', '.join(failed_list)}.)"
    else:
        status_str = "FAIL"

    md += "## Path Validation Status\n"
    md += f"- **TC7 Candidate Classification**: {status_str}\n"
    md += "- **TC7 Pro main path**: NOT_RUN\n"
    md += "- **Innovation actual search/tool_result integration**: NOT_RUN\n"
    md += "- **Production deployment**: HOLD\n\n"

    md += "## Function Inventory\n\n"
    md += "### candidate_policy.py\n"
    md += "| 함수명 | 역할 |\n| :--- | :--- |\n"
    md += "| `classify_candidates()` | tool_results → 5종 candidate_type 분류 |\n"
    md += "| `classify_candidate_types()` | classify_candidates 별칭 |\n"
    md += "| `get_candidate_counts()` | primary/tagged 분리 카운트 반환 |\n"
    md += "| `normalize_candidates()` | 후보 행 정규화 (auto_promoted=False 강제) |\n"
    md += "| `split_policy_companies()` | 조달등록 업체에서 정책기업 분리 → (local, policy) |\n"
    md += "| `build_required_checks()` | candidate_type별 필수 확인사항 반환 |\n"
    md += "| `get_data_source_status()` | 데이터 소스 연결 상태 반환 |\n"
    md += "| `_parse_company_line()` | MCP 결과 1행 파싱 (내부) |\n\n"

    md += "### candidate_formatter.py\n"
    md += "| 함수명 | 역할 |\n| :--- | :--- |\n"
    md += "| `format_candidate_tables()` | 분류 결과 → 구매 경로별 Markdown 표 (Pro/Flash 공용) |\n"
    md += "| `group_candidates_by_route()` | format_candidate_tables 별칭 |\n"
    md += "| `_determine_display_order()` | 사용자 키워드 기반 표시 순서 결정 (내부) |\n"
    md += "| `_build_company_table()` | 업체 후보 Markdown 표 생성 (내부) |\n"
    md += "| `_build_innovation_table()` | 혁신제품 후보 Markdown 표 생성 (내부) |\n\n"

    md += "## 카운터 산정 기준\n\n"
    md += "| 필드 | 기준 |\n| :--- | :--- |\n"
    md += "| `primary_policy_company_count` | `primary_candidate_type=policy_company`인 행 수 (분류 표에 실제 표시된 수) |\n"
    md += "| `tagged_policy_company_count` | `candidate_types` 배열에 `policy_company`가 포함된 전체 행 수 (다른 표에 분류되었더라도 포함) |\n\n"

    md += "## Raw JSON Output\n\n"
    for r in results:
        md += f"### {r['test_case']}\n"
        md += "```json\n"
        md += json.dumps(r, ensure_ascii=False, indent=2)
        md += "\n```\n\n"

    report_path = r"c:\Users\doors\.gemini\antigravity\brain\eaacb8aa-c5ce-4caf-9ea8-47f97d4c060c\artifacts\TC7_verification_result.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved to: {report_path}")
