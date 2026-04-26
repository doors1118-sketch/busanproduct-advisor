"""
TC7 후보군 분류체계 5종 확장 검증 스크립트 v2
- TC7-1: 종합쇼핑몰 등록 부산업체 후보
- TC7-2: 조달등록 부산업체 후보
- TC7-3: 정책기업 후보
- TC7-4: 혁신제품·혁신시제품 후보
- TC7-5: 우선구매·특례제품 data_source_status 확인
"""
import sys, os, json, re
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


# ── TC7-4: 혁신제품·혁신시제품 실제 연동 테스트 (제품명 검색) ──
def run_tc7_4():
    ds = get_data_source_status("innovation_product")

    # innovation_search import
    try:
        from policies.innovation_search import search_innovation_products, _load_innovation_metadata
        search_available = True
    except Exception as e:
        search_available = False
        return {
            "test_case": "TC7-4_Innovation_Product",
            "description": "혁신제품·혁신시제품 실제 연동 — import 실패",
            "pass": False,
            "failure_reason": f"import error: {e}",
        }

    # 테스트 쿼리 3건 (고정)
    test_queries = [
        "공기청정기 혁신제품 부산업체 찾아줘",
        "배전반 혁신시제품 찾아줘",
        "LED 관련 혁신제품 있어?",
    ]

    # 실제 데이터셋에서 known positive query 1건 자동 선택
    known_product_name = ""
    try:
        all_meta = _load_innovation_metadata()
        if all_meta:
            for item in all_meta:
                pn = str(item["meta"].get("product_name", ""))
                if pn and pn not in ("", "nan", "None"):
                    known_product_name = pn
                    break
    except Exception:
        pass

    if known_product_name:
        test_queries.append(f"{known_product_name} 혁신제품 찾아줘")

    # 모든 쿼리 실행
    all_results = []
    total_innov = 0
    total_pn_matched = 0
    total_cn_matched = 0
    total_low_conf = 0

    for q in test_queries:
        result = search_innovation_products(q, n_results=5)
        all_results.append(result)
        total_innov += result.get("innovation_product_count", 0)
        total_pn_matched += result.get("product_name_matched_count", 0)
        total_cn_matched += result.get("company_name_matched_count", 0)
        total_low_conf += result.get("low_confidence_count", 0)

    # 첫 번째 결과에서 sample rows 추출 (민감정보 검증)
    sample_rows = []
    sensitive_detected = []
    for res in all_results:
        for row in res.get("product_sample_rows", []):
            # 사업자등록번호·대표자명 미노출 검증
            row_str = json.dumps(row, ensure_ascii=False)
            if re.search(r"\d{3}-\d{2}-\d{5}", row_str):
                sensitive_detected.append("사업자등록번호_하이픈형")
            if re.search(r"^\d{10}$", row_str):
                # 10자리 숫자만으로는 오탐 가능 — biz_no 키 존재 여부 확인
                if "biz_no" in row:
                    sensitive_detected.append("biz_no_field_present")
            if "representative" in row:
                sensitive_detected.append("representative_field_present")
            sample_rows.append(row)

    auto_ok = all(
        r.get("contract_possible_auto_promoted") is False
        for res in all_results
        for r in res.get("product_sample_rows", [])
    )

    # known positive query가 있으면 최소 1건 이상 검색 결과 확인
    known_positive_pass = True
    if known_product_name and all_results:
        last_result = all_results[-1]
        if last_result.get("innovation_product_count", 0) == 0:
            known_positive_pass = False

    passed = (
        search_available
        and total_innov > 0
        and auto_ok
        and len(sensitive_detected) == 0
        and known_positive_pass
    )

    integration_status = "PASS" if passed else "READY_TO_IMPLEMENT"

    # unknown_cert_count 집계
    total_unknown_cert = sum(r.get("unknown_cert_count", 0) for r in all_results)
    total_valid_cert = sum(r.get("valid_cert_count", 0) for r in all_results)
    total_expired_cert = sum(r.get("expired_cert_count", 0) for r in all_results)

    return {
        "test_case": "TC7-4_Innovation_Product",
        "description": "혁신제품·혁신시제품 실제 로컬 검색 테스트 — 제품명 1순위 검색",
        "test_queries": test_queries,
        "known_product_name_used": known_product_name,
        "innovation_product_actual_search_integration": integration_status,
        "candidate_types_tested": ["innovation_product"],
        "primary_candidate_type": "innovation_product",
        "data_source_status": ds["data_source_status"],
        "runtime_tool_integration": ds.get("runtime_tool_integration", "pending"),
        "display_enabled": ds["display_enabled"],
        "staging_display_only": ds.get("staging_display_only", True),
        "production_display_enabled": ds.get("production_display_enabled", False),
        "innovation_product_count": total_innov,
        "product_name_matched_count": total_pn_matched,
        "company_name_matched_count": total_cn_matched,
        "low_confidence_count": total_low_conf,
        "valid_cert_count": total_valid_cert,
        "expired_cert_count": total_expired_cert,
        "unknown_cert_count": total_unknown_cert,
        "product_sample_rows": sample_rows[:5],
        "per_query_results": [
            {
                "query": r["query"],
                "query_intent": r.get("query_intent", ""),
                "product_name_query": r.get("product_name_query", ""),
                "innovation_product_count": r.get("innovation_product_count", 0),
                "product_name_matched_count": r.get("product_name_matched_count", 0),
                "company_name_matched_count": r.get("company_name_matched_count", 0),
                "match_basis_summary": [
                    row.get("match_basis", "") for row in r.get("product_sample_rows", [])
                ],
            }
            for r in all_results
        ],
        "contract_possible_auto_promoted": False,
        "legal_eligibility_status": "확인 필요",
        "required_checks": build_required_checks("innovation_product"),
        "caution_text_present": CANDIDATE_TYPES["innovation_product"].get("caution_text", "") != "",
        "sensitive_fields_removed": True,
        "sensitive_fields_detected": sensitive_detected,
        "known_positive_pass": known_positive_pass,
        "pass": passed,
        "failure_reason": "" if passed else (
            f"innov_count={total_innov}, auto_ok={auto_ok}, "
            f"sensitive={sensitive_detected}, known_positive={known_positive_pass}"
        ),
    }


# ── TC7-5: 기술개발제품 13종 실제 연동 테스트 ──
def run_tc7_5():
    ds = get_data_source_status("priority_purchase_product")
    meta = CANDIDATE_TYPES["priority_purchase_product"]

    try:
        from policies.innovation_search import search_tech_development_products
        search_available = True
    except Exception as e:
        search_available = False
        return {
            "test_case": "TC7-5_Priority_Purchase_Product",
            "description": "기술개발제품 13종 실제 연동 — import 실패",
            "pass": False,
            "failure_reason": f"import error: {e}",
        }

    result = search_tech_development_products("LED", max_results=5)
    rows = result.get("product_sample_rows", [])

    # 민감정보 미노출 검증
    sensitive_detected = []
    for row in rows:
        if "biz_no" in row:
            sensitive_detected.append("biz_no_field_present")
        if "representative" in row:
            sensitive_detected.append("representative_field_present")
        row_str = json.dumps(row, ensure_ascii=False)
        if re.search(r"\d{3}-\d{2}-\d{5}", row_str):
            sensitive_detected.append("사업자등록번호_하이픈형")

    auto_ok = all(r.get("contract_possible_auto_promoted") is False for r in rows)

    passed = (
        search_available
        and result.get("priority_purchase_count", 0) > 0
        and auto_ok
        and len(sensitive_detected) == 0
    )

    return {
        "test_case": "TC7-5_Priority_Purchase_Product",
        "description": "기술개발제품 13종 인증 보유 부산업체 실제 로컬 검색 테스트",
        "query": "LED",
        "candidate_types_tested": ["priority_purchase_product"],
        "primary_candidate_type": "priority_purchase_product",
        "data_source_status": ds["data_source_status"],
        "runtime_tool_integration": ds.get("runtime_tool_integration", "pending"),
        "display_enabled": ds["display_enabled"],
        "staging_display_only": ds.get("staging_display_only", True),
        "production_display_enabled": ds.get("production_display_enabled", False),
        "priority_purchase_count": result.get("priority_purchase_count", 0),
        "matched_business_no_count": result.get("matched_business_no_count", 0),
        "unmatched_tech_product_count": result.get("unmatched_tech_product_count", 0),
        "valid_cert_count": result.get("valid_cert_count", 0),
        "expired_cert_count": result.get("expired_cert_count", 0),
        "unknown_cert_count": result.get("unknown_cert_count", 0),
        "product_sample_rows": rows[:3],
        "contract_possible_auto_promoted": False,
        "legal_eligibility_status": "확인 필요",
        "required_checks": build_required_checks("priority_purchase_product"),
        "caution_text_present": meta.get("caution_text", "") != "",
        "sensitive_fields_removed": True,
        "sensitive_fields_detected": sensitive_detected,
        "pass": passed,
        "failure_reason": "" if passed else (
            f"count={result.get('priority_purchase_count', 0)}, "
            f"auto_ok={auto_ok}, sensitive={sensitive_detected}"
        ),
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
    md += "- **Innovation actual search integration**: " + ("PASS" if all_pass else "READY_TO_IMPLEMENT") + "\n"
    md += "- **Production deployment**: HOLD\n\n"

    md += "## Raw JSON Output\n\n"
    for r in results:
        md += f"### {r['test_case']}\n"
        md += "```json\n"
        md += json.dumps(r, ensure_ascii=False, indent=2)
        md += "\n```\n\n"

    report_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "TC7_verification_result.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved to: {report_path}")

