"""
Company Policy — contract_possible 자동 승격 방지 + 구조화 검증
"""
from prompting.schemas import CompanyResult, validate_company_result


def normalize_company_result(raw: dict) -> CompanyResult:
    """API 결과 dict → CompanyResult 구조화 객체 (contract_possible=False 강제)"""
    return CompanyResult(
        company_name=raw.get("업체명", ""),
        location=raw.get("소재지", ""),
        main_products=[raw.get("대표품명", "")],
        policy_tags=raw.get("_정책기업", []),
        tag_source="internal_policy_company_db",
        business_status=raw.get("_사업자상태", "unknown"),
        contract_possible=False,
        legal_eligibility_status="unverified",
        candidate_status="candidate",
    )


def format_company_for_llm(data: dict, max_results: int = 10) -> str:
    """
    검색 결과를 LLM에 전달할 텍스트로 변환.
    1차: 구조화 객체 검증, 2차: 문자열 보조 검증.
    """
    companies = data.get("업체목록", [])
    total = data.get("검색결과수", len(companies))

    if not companies:
        return "검색 결과가 없습니다."

    lines = [
        f"부산 지역업체 검색 결과: 총 {total}건 (상위 {min(max_results, len(companies))}건 표시)",
        "",
    ]

    for i, raw in enumerate(companies[:max_results]):
        # 1차: 구조화 검증
        result = normalize_company_result(raw)
        validate_company_result(result)

        line = f"{i+1}. {result.company_name}"
        if result.location:
            line += f" ({result.location})"
        if result.main_products and result.main_products[0]:
            line += f" -- {', '.join(result.main_products)}"
        if result.policy_tags:
            line += f" <{', '.join(result.policy_tags)}>"
        if result.business_status and result.business_status != "unknown":
            line += f" [{result.business_status}]"
        # 후보 상태 (contract_possible이 아닌 candidate_status)
        line += f" [{result.candidate_status}]"
        lines.append(line)

    if total > max_results:
        lines.append(f"\n... 외 {total - max_results}건")

    lines.append("")
    lines.append("📋 위 업체 목록은 조달청 등록 기준이며, 실제 계약 시 적격 여부를 별도 확인하세요.")
    lines.append("⚠️ 정책기업 태그는 후보 자격 정보이며, 수의계약 가능 여부는 법령·금액·견적 방식을 검증한 뒤 판단해야 합니다.")

    formatted = "\n".join(lines)

    # 2차: 문자열 보조 검증
    validate_no_contract_possible(formatted)

    return formatted


def validate_no_contract_possible(formatted: str) -> bool:
    """2차 보조 검증: 출력 텍스트에 contract_possible이 없는지 확인"""
    if "contract_possible" in formatted.lower():
        raise ValueError("contract_possible must not appear in formatted output")
    if "계약 가능" in formatted and "확인" not in formatted:
        raise ValueError("'계약 가능' without '확인' guard is not allowed")
    return True
