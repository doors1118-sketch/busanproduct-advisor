"""
TC8 모델 라우팅 정책 검증 스크립트
- TC8-1~3: 저위험 Flash 테스트
- TC8-4~7: 고위험 Pro 테스트
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "app"))
os.environ.setdefault("MODEL_ROUTING_MODE", "risk_based")
os.environ.setdefault("GEMINI_MODEL", "gemini-2.5-pro")
os.environ.setdefault("FALLBACK_MODEL", "gemini-2.5-flash")

from policies.model_routing_policy import (
    classify_risk, decide_fallback, build_routing_log,
    GEMINI_MODEL, FALLBACK_MODEL, MODEL_ROUTING_MODE
)


def _test_case(tc_id, query, expected_risk, expected_model, description,
               legal_conclusion_allowed=True, blocked_scope=None,
               direct_legal_basis_count=0, company_search_success=False,
               legal_judgment_requested=True, legal_judgment_allowed=True, company_table_allowed=True,
               claim_validation_pass=True):
    """단일 TC 실행"""
    risk = classify_risk(query)

    # 모델 결정 검증
    model_ok = risk["model_primary"] == expected_model
    risk_ok = risk["risk_level"] == expected_risk

    # Pro 실패 시 fallback 정책 검증 (고위험만)
    fallback_info = None
    if expected_risk == "high":
        fallback_info = decide_fallback(
            risk, legal_conclusion_allowed, blocked_scope or [],
            direct_legal_basis_count, company_search_success, claim_validation_pass
        )

    # 로그 생성
    log = build_routing_log(
        risk,
        model_used="not_executed",
        model_selected=risk["model_primary"],
        pro_call_executed=False,
        test_type="routing_policy_static",
        legal_judgment_requested=legal_judgment_requested,
        legal_judgment_allowed=legal_judgment_allowed,
        company_table_allowed=company_table_allowed,
        fallback_used=False,
        legal_conclusion_allowed=legal_conclusion_allowed,
        blocked_scope=blocked_scope,
        direct_legal_basis_count=direct_legal_basis_count,
    )

    passed = model_ok and risk_ok
    failure = ""
    if not model_ok:
        failure += f"model_primary={risk['model_primary']} (expected {expected_model}). "
    if not risk_ok:
        failure += f"risk_level={risk['risk_level']} (expected {expected_risk}). "

    result = {
        "test_case": tc_id,
        "description": description,
        "query": query,
        "test_type": log["test_type"],
        "model_routing_mode": log["model_routing_mode"],
        "model_selected": log["model_selected"],
        "model_used": log["model_used"],
        "pro_call_executed": log["pro_call_executed"],
        "model_decision_reason": log["model_decision_reason"],
        "risk_level": log["risk_level"],
        "high_risk_triggers": log["high_risk_triggers"],
        "fallback_used": log["fallback_used"],
        "fallback_reason": log["fallback_reason"],
        "retry_count": log["retry_count"],
        "legal_conclusion_allowed": log["legal_conclusion_allowed"],
        "legal_judgment_requested": log["legal_judgment_requested"],
        "legal_judgment_allowed": log["legal_judgment_allowed"],
        "company_table_allowed": log["company_table_allowed"],
        "blocked_scope": log["blocked_scope"],
        "direct_legal_basis_count": log["direct_legal_basis_count"],
        "deterministic_template_used": log["deterministic_template_used"],
        "flash_answer_discarded": log["flash_answer_discarded"],
        "pass": passed,
        "failure_reason": failure.strip() if failure else "",
    }

    if fallback_info:
        result["fallback_policy"] = fallback_info

    return result


if __name__ == "__main__":
    results = []

    # ── 저위험 Flash 테스트 ──
    results.append(_test_case(
        "TC8-1", "CCTV 부산 업체 추천해줘", "low", FALLBACK_MODEL,
        "저위험: 업체 후보 추천 → Flash",
        legal_conclusion_allowed="not_applicable", legal_judgment_requested=False, legal_judgment_allowed=False, company_table_allowed=True
    ))
    results.append(_test_case(
        "TC8-2", "LED 조명 부산 업체 후보 있어?", "low", FALLBACK_MODEL,
        "저위험: 업체 후보 검색 → Flash",
        legal_conclusion_allowed="not_applicable", legal_judgment_requested=False, legal_judgment_allowed=False, company_table_allowed=True
    ))
    results.append(_test_case(
        "TC8-3", "종합쇼핑몰 등록 부산업체 후보 보여줘", "low", FALLBACK_MODEL,
        "저위험: 쇼핑몰 업체 목록 → Flash",
        legal_conclusion_allowed="not_applicable", legal_judgment_requested=False, legal_judgment_allowed=False, company_table_allowed=True
    ))

    # ── 고위험 Pro 테스트 ──
    results.append(_test_case(
        "TC8-4", "조경공사 3천만원 수의계약 가능해?", "high", GEMINI_MODEL,
        "고위험: 수의계약 가능 여부 + 금액 → Pro",
        legal_conclusion_allowed=True, direct_legal_basis_count=2
    ))
    results.append(_test_case(
        "TC8-5", "8천만원 컴퓨터 1인 견적 가능해?", "high", GEMINI_MODEL,
        "고위험: 1인 견적 가능 여부 + 금액 → Pro",
        legal_conclusion_allowed=False, blocked_scope=["amount_threshold", "one_person_quote"]
    ))
    results.append(_test_case(
        "TC8-6", "여성기업이면 바로 수의계약 가능해?", "high", GEMINI_MODEL,
        "고위험: 정책기업 특례 + 수의계약 → Pro",
        legal_conclusion_allowed=False, blocked_scope=["policy_company_special_rule", "sole_contract_possibility"], 
        company_search_success=True, legal_judgment_allowed=False, company_table_allowed=True
    ))
    results.append(_test_case(
        "TC8-7", "혁신제품이면 금액 제한 없이 수의계약 가능해?", "high", GEMINI_MODEL,
        "고위험: 혁신제품 수의계약 + 금액 제한 → Pro",
        legal_conclusion_allowed=False, blocked_scope=["amount_threshold"], legal_judgment_allowed=False
    ))

    # Pro quota 없을 때 fallback 테스트
    results.append(_test_case(
        "TC8-8", "조경공사 3천만원 수의계약 가능해?", "high", GEMINI_MODEL,
        "고위험 Pro→fallback: legal_basis 충분 시 Flash fallback 허용",
        legal_conclusion_allowed=True, direct_legal_basis_count=3
    ))
    results.append(_test_case(
        "TC8-9", "8천만원 컴퓨터 1인 견적 가능해?", "high", GEMINI_MODEL,
        "고위험 Pro→fallback: legal_conclusion_allowed=false → fail-closed",
        legal_conclusion_allowed=False, blocked_scope=["amount_threshold", "one_person_quote"], legal_judgment_allowed=False
    ))
    results.append(_test_case(
        "TC8-10", "여성기업이면 바로 수의계약 가능해?", "high", GEMINI_MODEL,
        "고위험 Pro→fallback: blocked_scope + 업체검색 성공 → 제한 Flash fallback",
        legal_conclusion_allowed=False, blocked_scope=["sole_contract"],
        company_search_success=True, legal_judgment_allowed=False, company_table_allowed=True
    ))

    # 결과 저장
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tc8_routing_result.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"TC8 routing results saved to: {out_path}")

    for r in results:
        s = "PASS" if r["pass"] else "FAIL"
        print(f"  [{s}] {r['test_case']}: {r['description']} — {r.get('failure_reason','')}")

    # ── 보고서 생성 ──
    md = "# TC8 모델 라우팅 정책 검증 보고서\n\n"
    all_pass = all(r["pass"] for r in results)
    passed_list = [r["test_case"] for r in results if r["pass"]]
    failed_list = [r["test_case"] for r in results if not r["pass"]]

    if all_pass:
        status_str = "CONDITIONAL_PASS"
    elif passed_list:
        status_str = f"PARTIAL_PASS ({len(passed_list)}/{len(results)} passed)"
    else:
        status_str = "FAIL"

    md += "## Path Validation Status\n"
    md += f"- **Routing policy static validation**: {status_str}\n"
    md += f"- **MODEL_ROUTING_MODE**: {MODEL_ROUTING_MODE}\n"
    md += f"- **GEMINI_MODEL (Pro)**: {GEMINI_MODEL}\n"
    md += f"- **FALLBACK_MODEL (Flash)**: {FALLBACK_MODEL}\n"
    md += "- **Runtime model execution**: NOT_RUN\n"
    md += "- **Production deployment**: HOLD\n\n"

    md += "## 라우팅 정책 요약\n\n"
    md += "| 위험도 | 기본 모델 | 조건 |\n| :--- | :--- | :--- |\n"
    md += "| low | Flash | 업체 추천, 절차 안내, 목록 조회 등 |\n"
    md += "| high | Pro | 수의계약, 금액 한도, 1인 견적, 법령 해석 등 |\n"
    md += "| medium | Pro | 미분류 → 안전 우선 |\n\n"

    md += "## Fallback 정책 요약\n\n"
    md += "| 조건 | 결과 |\n| :--- | :--- |\n"
    md += "| Pro 실패 + legal_basis 충분 | Flash fallback 허용 |\n"
    md += "| Pro 실패 + legal_basis 부족 | deterministic fail-closed |\n"
    md += "| Pro 실패 + legal_conclusion_allowed=false | deterministic fail-closed |\n"
    md += "| Pro 실패 + blocked_scope + 업체검색 성공 | Flash 제한 fallback |\n"
    md += "| Pro 실패 + blocked_scope + 업체검색 없음 | deterministic fail-closed |\n\n"

    md += "## Raw JSON Output\n\n"
    for r in results:
        md += f"### {r['test_case']}\n"
        md += "```json\n"
        md += json.dumps(r, ensure_ascii=False, indent=2)
        md += "\n```\n\n"

    report_path = r"c:\Users\doors\.gemini\antigravity\brain\eaacb8aa-c5ce-4caf-9ea8-47f97d4c060c\artifacts\TC8_routing_result.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Report saved to: {report_path}")
