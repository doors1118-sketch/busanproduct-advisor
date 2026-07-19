"""
구매경로 판단 재료 생성 정책.

이 모듈은 최종 답변을 만들지 않는다. 금액·품목·업체검색 결과를 바탕으로
LLM이 실무형 답변을 작성할 때 참고할 "경로별 판단 재료"를 구조화한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from policies.numeric_basis_policy import compare_amount, get_numeric_display, get_numeric_value
except ImportError:  # package import path: app.policies.purchase_route_guidance_policy
    from importlib import import_module

    _numeric_basis_policy = import_module("app.policies.numeric_basis_policy")
    compare_amount = _numeric_basis_policy.compare_amount
    get_numeric_display = _numeric_basis_policy.get_numeric_display
    get_numeric_value = _numeric_basis_policy.get_numeric_value


@dataclass(frozen=True)
class PurchaseRouteCard:
    route_id: str
    title: str
    status: str
    user_label: str
    practical_meaning: str
    required_checks: list[str]
    evidence_topics: list[str]
    route_priority: str = "secondary"  # primary | secondary | excluded | reference
    display_policy: str = "show"  # show | brief | hide
    legal_refs: tuple[str, ...] = ()
    candidate_table_types: tuple[str, ...] = ()
    candidate_lookup_policy: str = "none"
    exclusion_reason: str = ""


_PRIORITY_LABELS = {
    "primary": "우선",
    "secondary": "보조",
    "excluded": "제외",
    "reference": "참고",
}

_ROUTE_TITLE_SHORT_LABELS = {
    "general_small_value_direct": "일반 1인견적",
    "two_quote_small_value": "지역제한 2인견적",
    "third_party_unit_price": "제3자단가계약 물품",
    "shopping_mall_mas": "종합쇼핑몰(MAS) 직접구매",
    "sme_competition_direct_production": "중기간경쟁/직접생산",
    "innovation_product": "혁신제품",
    "technology_development_product": "인증제품",
    "policy_company_one_quote": "정책기업 1인견적",
    "local_company_competitive": "부산업체 발굴",
    "service_small_value_direct": "용역 1인견적",
    "local_service_company": "부산 용역업체",
    "service_policy_candidate": "정책기업 용역",
    "construction_small_value_direct": "공사 수의계약",
    "construction_regional_restriction": "공사 지역제한",
    "construction_joint_contract": "공동도급",
    "construction_local_point": "지역업체 가점",
    "construction_license_company": "부산 공사업체",
}

_CANDIDATE_LOOKUP_LABELS = {
    "none": "후보표 없음",
    "shopping_mall": "종합쇼핑몰/MAS 후보표 연결",
    "local_company": "부산 조달등록 업체 후보표 연결",
    "policy_company": "정책기업 후보표 연결",
    "innovation_product": "혁신제품 후보표 연결",
    "priority_purchase_product": "기술개발제품 후보표 연결",
}

_CANDIDATE_TYPE_ORDER = [
    "shopping_mall_supplier",
    "local_procurement_company",
    "innovation_product",
    "priority_purchase_product",
    "policy_company",
]

_ROUTE_DISPLAY_ORDER = {
    "third_party_unit_price": 4,
    "shopping_mall_mas": 5,
    "two_quote_small_value": 20,
    "policy_company_one_quote": 30,
    "sme_competition_direct_production": 40,
    "local_company_competitive": 50,
    "technology_development_product": 60,
    "innovation_product": 70,
    "general_small_value_direct": 90,
    "service_two_quote_small_value": 10,
    "service_regional_restriction": 20,
    "local_service_company": 30,
    "service_policy_company": 40,
    "service_policy_candidate": 50,
    "service_small_value_direct": 90,
}

_ROUTE_PRIORITY_ORDER = {
    "primary": 0,
    "secondary": 1,
    "reference": 2,
    "excluded": 3,
}

_AGENCY_DISPLAY_LABELS = {
    "default": "미지정",
    "local_government": "지방자치단체",
    "local_gov": "지방자치단체",
    "national_agency": "국가기관",
    "national_gov": "국가기관",
    "central_government": "국가기관",
    "public_corporation": "공기업·준정부기관",
    "public_enterprise": "공기업·준정부기관",
    "public_agency": "공공기관",
}


def _count_from_result_text(result_text: str) -> int | None:
    text = str(result_text or "")
    if not text:
        return None
    if "업체 검색 API 호출에 실패" in text or "API 요청 실패" in text:
        return None
    if "검색 결과가 없습니다" in text:
        return 0
    m = re.search(r"총\s*(\d+)\s*건", text)
    if m:
        return int(m.group(1))
    numbered = re.findall(r"(?m)^\s*\d+\.\s+", text)
    if numbered:
        return len(numbered)
    return None


def _count_matching_raw_candidates(row: dict, item_name: str, candidate_type: str) -> int | None:
    payload = row.get("raw_result")
    if not isinstance(payload, dict):
        return None
    candidates = payload.get("candidates") or payload.get("data") or []
    if not isinstance(candidates, list):
        return None
    try:
        from policies.candidate_formatter import candidate_matches_user_item
    except Exception:
        return None
    return sum(
        1 for candidate in candidates
        if isinstance(candidate, dict)
        and candidate_matches_user_item(candidate, item_name, candidate_type=candidate_type)
    )


def _tool_counts(tool_results: list[dict] | None, item_name: str = "") -> dict[str, int | None]:
    counts: dict[str, int | None] = {
        "shopping_mall": None,
        "third_party_unit_price": None,
        "local_company": None,
        "local_license_company": None,
        "policy_company": None,
        "certified_product": None,
        "innovation_product": None,
    }
    def relevant_count(row: dict, fallback: int | None, candidate_type: str) -> int | None:
        if not item_name:
            return fallback
        raw_count = _count_matching_raw_candidates(row, item_name, candidate_type)
        return raw_count if raw_count is not None else fallback

    for row in tool_results or []:
        name = row.get("tool_name", "")
        count = _count_from_result_text(row.get("result", ""))
        if "shopping_mall" in name:
            count = relevant_count(row, count, "shopping_mall_supplier")
            counts["shopping_mall"] = max(counts["shopping_mall"] or 0, count or 0)
        elif "third_party_unit_price" in name or "third_party" in name or "제3자단가" in name:
            count = relevant_count(row, count, "shopping_mall_supplier")
            counts["third_party_unit_price"] = max(counts["third_party_unit_price"] or 0, count or 0)
        elif "company_by_license" in name:
            count = relevant_count(row, count, "local_procurement_company")
            counts["local_license_company"] = max(counts["local_license_company"] or 0, count or 0)
            counts["local_company"] = max(counts["local_company"] or 0, count or 0)
        elif "local_company" in name:
            count = relevant_count(row, count, "local_procurement_company")
            counts["local_company"] = max(counts["local_company"] or 0, count or 0)
        elif "company_by_policy" in name:
            count = relevant_count(row, count, "policy_company")
            counts["policy_company"] = (counts["policy_company"] or 0) + (count or 0)
        elif "certified_product" in name:
            count = relevant_count(row, count, "priority_purchase_product")
            counts["certified_product"] = max(counts["certified_product"] or 0, count or 0)
        elif "innovation_product" in name:
            count = relevant_count(row, count, "innovation_product")
            counts["innovation_product"] = max(counts["innovation_product"] or 0, count or 0)
    return counts


def _candidate_status(count: int | None) -> tuple[str, str]:
    if count is None:
        return "needs_lookup", "조회 필요"
    if count > 0:
        return "candidate_found", f"후보 {count}건"
    return "no_candidate_found", "후보 미확인"


def _money(parameter_ref: str) -> str:
    return get_numeric_display(parameter_ref) or "기준금액 확인 필요"


def _card(
    *,
    route_id: str,
    title: str,
    status: str,
    user_label: str,
    practical_meaning: str,
    required_checks: list[str],
    evidence_topics: list[str],
    route_priority: str = "secondary",
    display_policy: str = "show",
    legal_refs: list[str] | None = None,
    candidate_table_types: tuple[str, ...] = (),
    candidate_lookup_policy: str = "none",
    exclusion_reason: str = "",
) -> PurchaseRouteCard:
    return PurchaseRouteCard(
        route_id=route_id,
        title=title,
        status=status,
        user_label=user_label,
        practical_meaning=practical_meaning,
        required_checks=required_checks,
        evidence_topics=evidence_topics,
        route_priority=route_priority,
        display_policy=display_policy,
        legal_refs=tuple(legal_refs or evidence_topics),
        candidate_table_types=candidate_table_types,
        candidate_lookup_policy=candidate_lookup_policy,
        exclusion_reason=exclusion_reason,
    )


def _two_quote_status(amount: int | None) -> tuple[str, str, str, str]:
    ref = "P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD"
    threshold = _money(ref)
    compare = compare_amount(amount, ref)
    general_one_quote_value = get_numeric_value("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
    if (
        compare == "below_or_equal"
        and isinstance(general_one_quote_value, (int, float))
        and isinstance(amount, (int, float))
        and amount <= general_one_quote_value
    ):
        return (
            "viable_check",
            f"{threshold} 이하 2인 이상 견적도 가능",
            "질문 금액은 일반 1인 견적 검토 구간이므로 2인 이상 견적은 경쟁성을 높이는 대안 경로로 봅니다.",
            "secondary",
        )
    if compare == "below_or_equal":
        return (
            "viable_check",
            f"{threshold} 이하 2인 이상 견적 검토 가능",
            "질문 금액은 소액수의 2인 이상 견적 검토 구간에 들어오므로, 1인 견적이 어려운 경우에도 경쟁성 있는 견적 절차를 우선 검토할 수 있습니다.",
            "primary",
        )
    if compare == "above":
        return (
            "not_viable",
            f"{threshold} 초과로 소액 2인 견적 경로는 어려움",
            f"질문 금액이 소액수의 2인 이상 견적 검토 기준({threshold})을 초과하므로 경쟁입찰 또는 별도 특례를 우선 검토해야 합니다.",
            "excluded",
        )
    return (
        "needs_amount_check",
        "금액 확인 필요",
        "2인 이상 견적 소액수의 가능 여부는 추정가격과 계약대상별 기준 확인이 필요합니다.",
        "secondary",
    )


def _general_one_quote_goods_service(amount: int | None, object_label: str) -> tuple[str, str, str, str, str]:
    ref = "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD"
    threshold = _money(ref)
    compare = compare_amount(amount, ref)
    if compare == "above":
        return (
            "not_viable",
            f"일반 {threshold} 1인 견적 경로는 어려움",
            f"질문 금액은 일반 1인 견적 소액수의 기준({threshold})을 초과하므로 {object_label}을 이 경로로 바로 처리하기 어렵습니다.",
            "excluded",
            f"일반 1인 견적 기준({threshold}) 초과",
        )
    if compare == "below_or_equal":
        return (
            "viable_check",
            "일반 1인 견적 소액수의 검토 가능",
            f"확인된 기준({threshold}) 이하라면 일반 1인 견적 가능성을 우선 검토할 수 있습니다.",
            "primary",
            "",
        )
    return (
        "needs_amount_check",
        "금액 확인 필요",
        f"일반 1인 견적 소액수의 가능 여부는 {object_label}의 추정가격 기준 확인이 필요합니다.",
        "secondary",
        "",
    )


def _policy_one_quote(amount: int | None, object_label: str) -> tuple[str, str, str, str, str, str]:
    ref = "P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD"
    threshold = _money(ref)
    compare = compare_amount(amount, ref)
    general_one_quote_ref = "P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD"
    general_one_quote_threshold = _money(general_one_quote_ref)
    general_compare = compare_amount(amount, general_one_quote_ref)
    if compare == "above":
        return (
            "not_viable",
            f"{threshold} 1인 견적 경로는 어려움",
            f"여성기업·장애인기업·사회적기업 등 정책기업이라도 정책기업 1인 견적 기준({threshold})을 초과하면 {object_label}을 이 경로로 바로 처리하기 어렵습니다.",
            "excluded",
            "brief",
            f"정책기업 1인 견적 기준({threshold}) 초과",
        )
    if compare == "below_or_equal":
        if general_compare == "below_or_equal":
            return (
                "viable_check",
                "정책기업이면 함께 고려",
                (
                    f"질문 금액은 일반 1인 견적 기준({general_one_quote_threshold}) 안에 들어오므로 정책기업 요건이 최우선 경로는 아닙니다. "
                    "다만 부산 소재 여성기업·장애인기업·사회적기업이면 지역상품 구매와 사회적 가치 측면에서 후보 선별 기준으로 함께 볼 수 있습니다."
                ),
                "secondary",
                "show",
                "",
            )
        return (
            "viable_check",
            "정책기업 1인 견적 검토 가능",
            f"확인된 기준({threshold}) 이하라면 정책기업 지위와 증빙자료를 확인해 1인 견적 가능성을 검토할 수 있습니다.",
            "primary",
            "show",
            "",
        )
    return (
        "needs_amount_check",
        "금액 확인 필요",
        "정책기업 1인 견적 경로는 기업유형, 추정가격, 증빙자료 확인이 필요합니다.",
        "secondary",
        "show",
        "",
    )


def _candidate_priority(status: str, default: str = "secondary") -> str:
    return default


def _is_likely_sme_competition_item(item_name: str) -> bool:
    compact = re.sub(r"\s+", "", str(item_name or "")).lower()
    return any(
        term in compact
        for term in (
            "노트북",
            "노트북컴퓨터",
            "휴대용컴퓨터",
            "컴퓨터",
            "데스크톱컴퓨터",
        )
    )


def _mas_route_status(
    *,
    amount: int | None,
    item_name: str,
    candidate_count: int | None,
) -> tuple[str, str, str, str]:
    candidate_status, candidate_label = _candidate_status(candidate_count)
    mas_general_threshold = _money("P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD")
    mas_sme_threshold = _money("P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD")
    general_value = get_numeric_value("P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD")
    sme_value = get_numeric_value("P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD")
    general_one_quote_value = get_numeric_value("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
    likely_sme = _is_likely_sme_competition_item(item_name)

    def direct_purchase_priority() -> str:
        if (
            isinstance(general_one_quote_value, (int, float))
            and isinstance(amount, (int, float))
            and amount <= general_one_quote_value
        ):
            return "secondary"
        return "primary"

    if amount is None or not isinstance(general_value, (int, float)) or not isinstance(sme_value, (int, float)):
        base = (
            "needs_lookup",
            "금액·품목 확인 필요",
            "종합쇼핑몰 등록 여부, 세부품명, 2단계 경쟁 기준 금액을 함께 확인해야 합니다.",
            "secondary",
        )
        if candidate_count is not None:
            return candidate_status, candidate_label, base[2], _candidate_priority(candidate_status, "secondary")
        return base

    if amount < general_value:
        meaning = (
            f"{item_name or '해당 물품'} 품목이 종합쇼핑몰/MAS 등록 물품이면 일반 제품 기준({mas_general_threshold})에도 못 미치므로 "
            "2단계 경쟁보다 납품요구·직접구매 가능성을 먼저 확인합니다."
        )
        if likely_sme:
            meaning += (
                f" 노트북·컴퓨터류가 중소기업자간 경쟁제품 세부품명에 해당하면 기준은 {mas_sme_threshold} 이상이므로, "
                "질문 금액은 2단계 경쟁 기준 미만입니다."
            )
        return "mas_direct_check", "2단계 기준 미만", meaning, direct_purchase_priority()

    if likely_sme and amount < sme_value:
        meaning = (
            f"{item_name or '해당 물품'} 품목이 중소기업자간 경쟁제품 세부품명에 해당하면 MAS 2단계 경쟁 기준은 "
            f"{mas_sme_threshold} 이상이므로 질문 금액은 직접구매 가능성을 먼저 확인합니다. "
            f"다만 일반 제품으로 보면 {mas_general_threshold} 이상 구간이므로 세부품명 확인이 필요합니다."
        )
        return (
            "mas_direct_check",
            "중기제품 직접구매 우선",
            meaning,
            direct_purchase_priority(),
        )

    meaning = (
        f"종합쇼핑몰/MAS 등록 물품이라도 일반 제품은 {mas_general_threshold}, "
        f"중소기업자간 경쟁제품은 {mas_sme_threshold} 이상이면 2단계 경쟁 대상 여부를 확인해야 합니다."
    )
    if candidate_count is not None:
        return candidate_status, candidate_label, meaning, _candidate_priority(candidate_status, "secondary")
    return (
        "mas_second_stage_check",
        "2단계 경쟁 확인",
        meaning,
        "secondary",
    )


def _agency_procurement_obligation_note(agency_type: str | None) -> str:
    agency = (agency_type or "").lower()
    if agency in {"national_agency", "national_gov", "central_government"}:
        return "국가기관은 1억원 이상 물품·용역 및 단가계약 물품이 조달청 구매 검토 대상입니다."
    if agency in {"local_government", "local_gov"}:
        return "지방자치단체와 교육기관은 단가계약 물품이면 조달청 구매 검토 대상입니다."
    if agency in {"public_corporation", "public_enterprise", "public_agency"}:
        return "공기업·준정부기관은 중기간 경쟁제품 고시금액 이상 등 별도 위탁 기준과 기관 내부규정 확인이 필요합니다."
    return "기관유형에 따라 조달청구매 대상 여부가 달라지므로 국가기관·지방자치단체·공기업/준정부기관 구분을 확인해야 합니다."


def _third_party_unit_price_status(
    *,
    candidate_count: int | None,
    agency_type: str | None,
) -> tuple[str, str, str, str, str]:
    agency_note = _agency_procurement_obligation_note(agency_type)
    if candidate_count and candidate_count > 0:
        return (
            "candidate_found",
            f"제3자단가 근거 {candidate_count}건",
            (
                "공식 쇼핑몰/계약상품 원천에서 계약유형이 제3자단가계약으로 확인되는 물품은 "
                "조달청 종합쇼핑몰 납품요구 경로를 먼저 확인합니다. "
                f"{agency_note}"
            ),
            "primary",
            "",
        )
    if candidate_count == 0:
        return (
            "no_candidate_found",
            "제3자단가 근거 미확인",
            (
                "현재 후보 DB에서는 제3자단가계약 계약유형이 확인되지 않았습니다. "
                "MAS·일반 쇼핑몰 등록 또는 수요기관 직접구매 가능성을 분리해서 봐야 합니다."
            ),
            "reference",
            "제3자단가 계약유형 근거 없음",
        )
    return (
        "needs_lookup",
        "조달청 단가계약 근거 미확인",
        (
            "품목명만으로는 제3자단가계약 여부를 확정하지 않습니다. "
            "조달청 종합쇼핑몰 품목 등록 내역의 계약유형, 물품식별번호, 계약기간을 확인해야 합니다. "
            f"{agency_note}"
        ),
        "reference",
        "",
    )


def build_purchase_route_cards(
    *,
    amount: int | None,
    item_name: str,
    contract_object: str | None = None,
    agency_type: str | None = None,
    tool_results: list[dict] | None = None,
) -> list[PurchaseRouteCard]:
    """금액·품목·조회 결과를 경로별 판단 카드로 만든다."""
    object_type = (contract_object or "goods").lower()
    counts = _tool_counts(tool_results, item_name)

    if object_type == "service":
        return _build_service_route_cards(amount, item_name, counts)
    if object_type == "construction":
        return _build_construction_route_cards(amount, item_name, counts)

    general_status, general_label, general_meaning, general_priority, general_exclusion = (
        _general_one_quote_goods_service(amount, "물품")
    )
    policy_status, policy_label, policy_meaning, policy_priority, policy_display, policy_exclusion = (
        _policy_one_quote(amount, "물품")
    )
    two_status, two_label, two_meaning, two_priority = _two_quote_status(amount)
    shopping_status, shopping_label, shopping_meaning, shopping_priority = _mas_route_status(
        amount=amount,
        item_name=item_name,
        candidate_count=counts["shopping_mall"],
    )
    third_status, third_label, third_meaning, third_priority, third_exclusion = _third_party_unit_price_status(
        candidate_count=counts.get("third_party_unit_price"),
        agency_type=agency_type,
    )
    if (
        shopping_status == "mas_direct_check"
        and shopping_priority == "primary"
        and policy_priority == "primary"
    ):
        policy_priority = "secondary"
        policy_meaning = (
            f"{policy_meaning} 다만 종합쇼핑몰/MAS 등록 가능성이 높은 물품은 "
            "쇼핑몰 계약상태와 납품요구 가능성을 먼저 확인하고, 정책기업 1인 견적은 "
            "부산 소재 정책기업의 품목·증빙·가격 적정성이 명확할 때 쓰는 예외 경로로 봅니다."
        )
    cert_status, cert_label = _candidate_status(counts["certified_product"])
    innovation_status, innovation_label = _candidate_status(counts["innovation_product"])
    local_status, local_label = _candidate_status(counts["local_company"])

    return [
        _card(
            route_id="general_small_value_direct",
            title="일반 물품 소액수의(1인 견적)",
            status=general_status,
            user_label=general_label,
            practical_meaning=general_meaning,
            required_checks=["추정가격/부가세 포함 여부", "1인 견적 가능 사유", "기관유형별 적용 기준"],
            evidence_topics=["direct_contract", "one_person_quote", "amount_threshold"],
            route_priority=general_priority,
            display_policy="brief" if general_status == "not_viable" else "show",
            legal_refs=["지방계약법 시행령 제25조", "지방계약법 시행령 제30조", "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령"],
            exclusion_reason=general_exclusion,
        ),
        _card(
            route_id="two_quote_small_value",
            title="2인 이상 견적 소액수의",
            status=two_status,
            user_label=two_label,
            practical_meaning=two_meaning,
            required_checks=["추정가격", "2인 이상 견적 제출", "소기업·소상공인 또는 제한 가능 요건", "품목별 예외"],
            evidence_topics=["direct_contract", "two_quote", "amount_threshold"],
            route_priority=two_priority,
            display_policy="brief" if two_status == "not_viable" else "show",
            legal_refs=["지방계약법 시행령 제25조", "지방계약법 시행령 제30조", "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
        _card(
            route_id="third_party_unit_price",
            title="제3자단가계약 물품",
            status=third_status,
            user_label=third_label,
            practical_meaning=third_meaning,
            required_checks=["계약유형=제3자단가계약", "물품식별번호", "계약기간/계약상태", "납품요구 가능 여부", "기관유형별 조달청구매 대상 여부"],
            evidence_topics=["third_party_unit_price", "shopping_mall", "central_procurement"],
            route_priority=third_priority,
            display_policy="brief" if third_status == "no_candidate_found" else "show",
            legal_refs=["조달사업에 관한 법률 제11조", "조달사업에 관한 법률 시행령 제11조", "조달사업에 관한 법률 제12조", "조달청 종합쇼핑몰 품목 등록 내역"],
            candidate_table_types=("shopping_mall_supplier",),
            candidate_lookup_policy="shopping_mall",
            exclusion_reason=third_exclusion,
        ),
        _card(
            route_id="shopping_mall_mas",
            title="종합쇼핑몰/MAS",
            status=shopping_status,
            user_label=shopping_label,
            practical_meaning=shopping_meaning,
            required_checks=["쇼핑몰 계약상태", "공급업체 소재지", "납품 가능 지역", "규격 일치", "2단계 경쟁 대상 여부"],
            evidence_topics=["mas", "shopping_mall", "regional_factor"],
            route_priority=shopping_priority,
            legal_refs=["나라장터 종합쇼핑몰 운영규정", "물품 다수공급자계약 업무처리규정", "물품 다수공급자계약 2단계경쟁 업무처리기준"],
            candidate_table_types=("shopping_mall_supplier",),
            candidate_lookup_policy="shopping_mall",
        ),
        _card(
            route_id="sme_competition_direct_production",
            title="중소기업자간 경쟁제품/직접생산확인",
            status="viable_check",
            user_label="품목 해당 여부 우선 확인",
            practical_meaning="물품은 세부품명이 중소기업자간 경쟁제품 또는 직접생산확인 대상인지 먼저 확인해야 하며, 해당되면 참가자격과 후보 업체 풀이 달라집니다.",
            required_checks=["세부품명번호", "중소기업자간 경쟁제품 해당 여부", "직접생산확인 필요 여부", "부산 소재 조달업체 여부"],
            evidence_topics=["sme_competition", "direct_production", "local_company"],
            route_priority="reference",
            legal_refs=["중소기업제품 구매촉진 및 판로지원에 관한 법률", "중소기업자간 경쟁제품 직접생산 확인기준"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
        _card(
            route_id="innovation_product",
            title="혁신제품/혁신시제품",
            status=innovation_status,
            user_label=innovation_label,
            practical_meaning="혁신제품 또는 혁신시제품 후보가 있으면 지정 상태와 제품 일치 여부를 확인한 뒤 수의계약 특례·혁신장터 구매 가능성을 검토합니다.",
            required_checks=["혁신제품 지정 상태", "혁신장터 등록 여부", "구매 품목과 지정 제품의 일치", "수요기관 적용 법령"],
            evidence_topics=["innovation_product", "priority_purchase", "direct_contract_exception"],
            route_priority=_candidate_priority(innovation_status, "reference"),
            legal_refs=["혁신제품 구매 운영 규정", "혁신제품 시범구매계약 추가특수조건"],
            candidate_table_types=("innovation_product",),
            candidate_lookup_policy="innovation_product",
        ),
        _card(
            route_id="technology_development_product",
            title="기술개발제품/우수조달 등 인증제품",
            status=cert_status,
            user_label=cert_label,
            practical_meaning="성능인증, NEP, NET, GS, 우수조달물품 등 인증제품 후보가 있으면 우선구매 또는 수의계약 가능성을 검토합니다.",
            required_checks=["인증 유형", "인증 상태", "인증제품명과 구매품목 일치", "조달등록 또는 쇼핑몰 등록 여부"],
            evidence_topics=["technology_development_product", "priority_purchase", "excellent_procurement"],
            route_priority=_candidate_priority(cert_status, "reference"),
            legal_refs=["중소기업제품 구매촉진 및 판로지원에 관한 법률", "중소기업제품 구매촉진법 시행령", "우수조달물품 지정관리 규정"],
            candidate_table_types=("priority_purchase_product",),
            candidate_lookup_policy="priority_purchase_product",
        ),
        _card(
            route_id="policy_company_one_quote",
            title="정책기업 1인 견적",
            status=policy_status,
            user_label=policy_label,
            practical_meaning=policy_meaning,
            required_checks=["정책기업 유형", "증빙자료", "견적 방식", "기관유형별 한도"],
            evidence_topics=["policy_company", "one_person_quote", "amount_threshold"],
            route_priority=policy_priority,
            display_policy=policy_display,
            legal_refs=["지방계약법 시행령 제25조", "지방계약법 시행령 제30조", "여성기업지원법", "장애인기업활동 촉진법", "사회적기업 육성법"],
            candidate_table_types=("policy_company",),
            candidate_lookup_policy="policy_company",
            exclusion_reason=policy_exclusion,
        ),
        _card(
            route_id="local_company_competitive",
            title="부산 지역업체 경쟁/후보 발굴",
            status=local_status,
            user_label=local_label,
            practical_meaning="수의계약이 곧바로 어렵거나 견적 경쟁이 필요하면 부산 조달등록 업체를 후보로 놓고 지역제한, 평가요소, 쇼핑몰 경로를 함께 검토합니다.",
            required_checks=["부산 소재 여부", "조달등록/영업상태", "직접생산확인", "면허·업종·규격 적합성"],
            evidence_topics=["regional_restriction", "local_company_point", "direct_production"],
            route_priority=_candidate_priority(local_status, "reference"),
            legal_refs=["지방계약법 시행규칙 제24조", "지방자치단체 입찰시 낙찰자 결정기준", "지역업체 정의"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
    ]


def _build_service_route_cards(amount: int | None, item_name: str, counts: dict[str, int | None]) -> list[PurchaseRouteCard]:
    general_status, general_label, general_meaning, general_priority, general_exclusion = (
        _general_one_quote_goods_service(amount, "용역")
    )
    policy_status, policy_label, policy_meaning, policy_priority, policy_display, policy_exclusion = (
        _policy_one_quote(amount, "용역")
    )
    two_status, two_label, two_meaning, two_priority = _two_quote_status(amount)
    if two_priority == "primary" and policy_priority == "primary":
        policy_priority = "secondary"
        policy_meaning = (
            f"{policy_meaning} 다만 일반 1인 견적 기준을 넘는 용역에서는 "
            "부산 지역제한 2인 이상 견적을 기본 경로로 두고, 정책기업 1인 견적은 "
            "해당 자격·증빙이 명확한 경우의 예외적 단축 경로로 검토합니다."
        )
    local_status, local_label = _candidate_status(counts.get("local_license_company") or counts.get("local_company"))
    policy_candidate_status, policy_candidate_label = _candidate_status(counts.get("policy_company"))
    policy_candidate_display = "hide" if policy_status == "not_viable" else "show"

    return [
        _card(
            route_id="service_small_value_direct",
            title="일반 용역 소액수의(1인 견적)",
            status=general_status,
            user_label=general_label,
            practical_meaning=general_meaning,
            required_checks=["추정가격/부가세 포함 여부", "1인 견적 가능 사유", "용역 종류", "기관유형별 기준"],
            evidence_topics=["direct_contract", "one_person_quote", "amount_threshold"],
            route_priority=general_priority,
            display_policy="brief" if general_status == "not_viable" else "show",
            legal_refs=["지방계약법 시행령 제25조", "지방계약법 시행령 제30조", "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령"],
            exclusion_reason=general_exclusion,
        ),
        _card(
            route_id="service_two_quote_small_value",
            title="용역 2인 이상 견적 소액수의",
            status=two_status,
            user_label=two_label,
            practical_meaning=(
                f"{two_meaning} 부산업체 우대를 목표로 한다면 G2B 견적 공고에서 "
                "부산 소재 업체로 지역 제한을 걸 수 있는지 먼저 검토합니다."
            ),
            required_checks=["추정가격", "용역 종류", "2인 이상 견적", "과업 범위와 참가자격"],
            evidence_topics=["direct_contract", "two_quote", "amount_threshold", "regional_restriction"],
            route_priority=two_priority,
            display_policy="brief" if two_status == "not_viable" else "show",
            legal_refs=[
                "지방계약법 시행령 제25조",
                "지방계약법 시행령 제30조",
                "지방계약법 시행규칙 제24조",
            ],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
        _card(
            route_id="service_policy_company",
            title="정책기업 용역 1인 견적",
            status=policy_status,
            user_label=policy_label,
            practical_meaning=policy_meaning,
            required_checks=["정책기업 유형", "증빙자료", "용역 수행 가능 업종", "견적 방식"],
            evidence_topics=["policy_company", "one_person_quote", "amount_threshold"],
            route_priority=policy_priority,
            display_policy=policy_display,
            legal_refs=["지방계약법 시행령 제25조", "지방계약법 시행령 제30조", "여성기업지원법", "장애인기업활동 촉진법", "사회적기업 육성법"],
            candidate_table_types=("policy_company",),
            candidate_lookup_policy="policy_company",
            exclusion_reason=policy_exclusion,
        ),
        _card(
            route_id="service_regional_restriction",
            title="지역제한/지역업체 참여 용역",
            status="viable_check",
            user_label="조건부 검토",
            practical_meaning="수의계약이 어렵다면 용역 특성과 금액에 맞춰 지역제한, 참가자격, 평가요소를 통해 부산 업체 참여 가능성을 검토합니다.",
            required_checks=["지역제한 가능 금액", "업종·면허 제한 가능성", "과업 범위", "평가항목 반영 가능성"],
            evidence_topics=["regional_restriction", "local_company_point", "service_evaluation"],
            route_priority="secondary",
            legal_refs=["지방계약법 시행규칙 제24조", "지방자치단체 입찰 및 계약집행기준", "지방자치단체 입찰시 낙찰자 결정기준"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
        _card(
            route_id="local_service_company",
            title="부산 용역업체 후보",
            status=local_status,
            user_label=local_label,
            practical_meaning="과업명 또는 면허·업종으로 부산 업체 후보를 찾고, 실제 수행능력과 면허를 확인합니다.",
            required_checks=["부산 소재 여부", "해당 용역 면허·업종", "실적·인력·장비", "영업상태"],
            evidence_topics=["local_company", "license", "service_capability"],
            route_priority=_candidate_priority(local_status),
            legal_refs=["지역업체 정의", "입찰참가자격", "용역 수행능력 평가"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
        _card(
            route_id="service_policy_candidate",
            title="정책기업 용역 후보",
            status=policy_candidate_status,
            user_label=policy_candidate_label,
            practical_meaning="정책기업 후보는 금액상 정책기업 1인 견적 경로가 살아 있을 때 별도 후보표로 연결하고, 그렇지 않으면 업체의 부가속성으로만 확인합니다.",
            required_checks=["정책기업 지위", "용역 수행 업종", "증빙자료", "견적 방식"],
            evidence_topics=["policy_company", "direct_contract"],
            route_priority=_candidate_priority(policy_candidate_status, "reference"),
            display_policy=policy_candidate_display,
            legal_refs=["지방계약법 시행령 제25조", "지방계약법 시행령 제30조", "정책기업 수의계약"],
            candidate_table_types=("policy_company",),
            candidate_lookup_policy="policy_company",
        ),
    ]


def _construction_direct_status(amount: int | None) -> tuple[str, str, str, str, str]:
    general = get_numeric_value("P_DIRECT_GENERAL_CONSTRUCTION_THRESHOLD")
    specialty = get_numeric_value("P_DIRECT_SPECIALTY_CONSTRUCTION_THRESHOLD")
    other = get_numeric_value("P_DIRECT_OTHER_CONSTRUCTION_THRESHOLD")
    general_label = _money("P_DIRECT_GENERAL_CONSTRUCTION_THRESHOLD")
    specialty_label = _money("P_DIRECT_SPECIALTY_CONSTRUCTION_THRESHOLD")
    other_label = _money("P_DIRECT_OTHER_CONSTRUCTION_THRESHOLD")
    if amount is None or not all(isinstance(v, (int, float)) for v in (general, specialty, other)):
        return (
            "needs_amount_check",
            "금액·공종 확인 필요",
            "공사는 공종, 추정가격, 전문/종합 여부에 따라 수의계약·지역제한·공동도급 검토 방식이 달라집니다.",
            "secondary",
            "",
        )
    if amount <= other:
        return (
            "viable_check",
            f"{other_label} 이하 공사 수의계약 검토 가능",
            f"그 밖의 공사 기준({other_label}) 이하 금액대이므로 공종별 요건과 예외사유를 확인해 수의계약 가능성을 검토할 수 있습니다.",
            "primary",
            "",
        )
    if amount <= general:
        return (
            "viable_check",
            "공종별 수의계약 한도 확인 필요",
            f"공사는 종합공사 {general_label}, 전문공사 {specialty_label}, 그 밖의 공사 {other_label} 등 공종별 기준이 달라 공종 확정 후 판단해야 합니다.",
            "primary",
            "",
        )
    return (
        "not_viable",
        f"일반 공사 수의계약 기준({general_label}) 초과",
        f"질문 금액이 일반 공사 수의계약 기준({general_label})을 초과하므로 경쟁입찰, 지역제한, 공동계약 경로를 우선 검토해야 합니다.",
        "excluded",
        f"공사 수의계약 기준({general_label}) 초과",
    )


def _build_construction_route_cards(amount: int | None, item_name: str, counts: dict[str, int | None]) -> list[PurchaseRouteCard]:
    direct_status, direct_label, direct_meaning, direct_priority, direct_exclusion = _construction_direct_status(amount)
    local_status, local_label = _candidate_status(counts.get("local_license_company") or counts.get("local_company"))

    return [
        _card(
            route_id="construction_direct_contract",
            title="공사 수의계약",
            status=direct_status,
            user_label=direct_label,
            practical_meaning=direct_meaning,
            required_checks=["추정가격", "종합/전문공사 구분", "공종", "예외적 수의계약 사유"],
            evidence_topics=["direct_contract", "construction_threshold", "amount_threshold"],
            route_priority=direct_priority,
            display_policy="brief" if direct_status == "not_viable" else "show",
            legal_refs=["지방계약법 시행령 제25조", "국가계약법 시행령 제26조", "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령"],
            candidate_table_types=("local_procurement_company",) if direct_status != "not_viable" else (),
            candidate_lookup_policy="local_company" if direct_status != "not_viable" else "none",
            exclusion_reason=direct_exclusion,
        ),
        _card(
            route_id="construction_regional_restriction",
            title="공사 지역제한 입찰",
            status="viable_check",
            user_label="조건부 검토",
            practical_meaning="금액과 공종이 기준에 맞으면 부산 지역업체로 참가자격을 제한하는 방안을 검토할 수 있습니다.",
            required_checks=["종합/전문공사 구분", "지역제한 기준금액", "공사현장 소재지", "면허 요건"],
            evidence_topics=["regional_restriction", "construction_threshold", "local_company"],
            route_priority="secondary",
            legal_refs=["지방계약법 시행규칙 제24조", "지역제한 입찰 기준"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
        _card(
            route_id="construction_joint_contract",
            title="지역의무공동도급/공동수급",
            status="viable_check",
            user_label="조건부 검토",
            practical_meaning="대형 공사나 공동계약이 가능한 사안이면 지역업체 의무참여 또는 공동수급 구조를 검토합니다.",
            required_checks=["공동계약 허용 여부", "지역업체 참여비율", "공종 분담 가능성", "발주기관 기준"],
            evidence_topics=["joint_contract", "regional_joint_contract", "local_company"],
            route_priority="secondary",
            legal_refs=["공동계약 운영요령", "지역의무공동도급"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
        _card(
            route_id="construction_local_company_points",
            title="지역업체 참여도/가점",
            status="viable_check",
            user_label="조건부 검토",
            practical_meaning="적격심사·종합평가 등에서 지역업체 참여도나 신인도 요소를 반영할 수 있는지 확인합니다.",
            required_checks=["낙찰자 결정방식", "평가기준", "지역업체 인정 기준", "공고문 반영 가능성"],
            evidence_topics=["local_company_point", "evaluation_points", "regional_factor"],
            route_priority="secondary",
            legal_refs=["지방자치단체 입찰시 낙찰자 결정기준", "지역업체 참여도"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
        _card(
            route_id="local_construction_company",
            title="부산 공사업체 후보",
            status=local_status,
            user_label=local_label,
            practical_meaning="공종·면허 기준으로 부산 업체 후보를 찾고, 면허·시공능력·실적을 확인합니다.",
            required_checks=["부산 소재 여부", "공사업 면허", "시공능력/실적", "영업상태"],
            evidence_topics=["local_company", "license", "construction_capability"],
            route_priority=_candidate_priority(local_status),
            legal_refs=["지역업체 정의", "입찰참가자격", "공사업 면허"],
            candidate_table_types=("local_procurement_company",),
            candidate_lookup_policy="local_company",
        ),
    ]


def derive_candidate_table_display_options(cards: list[PurchaseRouteCard]) -> dict[str, list[str]]:
    """구매경로 카드 판단을 후보표 포맷터 옵션으로 변환한다."""
    visible: set[str] = set()
    hidden: set[str] = set()
    for card in cards:
        candidate_types = set(card.candidate_table_types or ())
        if not candidate_types:
            continue
        if card.display_policy == "hide" or card.route_priority == "excluded":
            hidden.update(candidate_types)
        else:
            visible.update(candidate_types)

    hidden -= visible
    preferred = [ct for ct in _CANDIDATE_TYPE_ORDER if ct in visible and ct not in hidden]
    return {
        "hidden_candidate_types": [ct for ct in _CANDIDATE_TYPE_ORDER if ct in hidden],
        "preferred_candidate_order": preferred,
    }


def _format_candidate_lookup(card: PurchaseRouteCard) -> str:
    label = _CANDIDATE_LOOKUP_LABELS.get(card.candidate_lookup_policy, card.candidate_lookup_policy)
    if card.display_policy in {"hide", "brief"} and card.route_priority == "excluded":
        return "별도 후보표 생략"
    return label


def _format_route_display_title(card: PurchaseRouteCard) -> str:
    return _ROUTE_TITLE_SHORT_LABELS.get(card.route_id, card.title)


def _format_route_display_judgment(card: PurchaseRouteCard) -> str:
    if card.status == "candidate_found":
        return card.user_label
    if card.status == "no_candidate_found":
        return "후보 미확인"
    if card.status == "needs_lookup":
        return "확인 필요"
    if card.route_priority == "excluded":
        amount_match = re.search(r"(\d+[천만억]+원?)", card.user_label)
        return f"{amount_match.group(1)} 초과" if amount_match else "기준 초과"
    if "품목 해당" in card.user_label:
        return "품목 확인"
    if "검토 가능" in card.user_label:
        return "검토 가능"
    return card.user_label


def _format_route_display_priority(card: PurchaseRouteCard, rank: int) -> str:
    if card.route_priority == "excluded":
        return "제외"
    if card.route_id == "sme_competition_direct_production":
        return "필수확인"
    if card.route_priority == "reference":
        return "참고"
    return f"{rank}순위"


def _route_display_sort_key(card: PurchaseRouteCard) -> tuple[int, int, str]:
    return (
        _ROUTE_PRIORITY_ORDER.get(card.route_priority, 9),
        _ROUTE_DISPLAY_ORDER.get(card.route_id, 80),
        card.route_id,
    )


def format_purchase_route_guidance_for_llm(
    *,
    amount: int | None,
    item_name: str,
    contract_object: str | None = None,
    agency_type: str | None = None,
    tool_results: list[dict] | None = None,
) -> str:
    cards = build_purchase_route_cards(
        amount=amount,
        item_name=item_name,
        contract_object=contract_object,
        agency_type=agency_type,
        tool_results=tool_results,
    )
    amount_label = f"{amount:,}원" if amount is not None else "미확인"
    agency_label = _AGENCY_DISPLAY_LABELS.get(agency_type or "default", agency_type or "미지정")
    object_label = {
        "goods": "물품",
        "service": "용역",
        "construction": "공사",
    }.get((contract_object or "goods").lower(), "미지정")
    lines = [
        "",
        "[구매경로 판단 재료 — 최종 답변은 아래 경로를 조합해 실무형으로 작성]",
        f"- 계약대상: {object_label}",
        f"- 품목/과업/공종: {item_name or '미확인'}",
        f"- 금액: {amount_label}",
        f"- 기관유형: {agency_label}",
        "- 작성 원칙: 주경로를 먼저 설명하고, 제외 경로는 이유만 짧게 정리한다.",
        "- 작성 원칙: 구매경로 판단에는 경로별 법적 근거를 반드시 함께 제시한다. 근거가 약하거나 적용 여부가 불명확하면 '확인 필요'로 표시한다.",
        "- 작성 원칙: 후보표는 구매경로 판단과 맞는 표만 사용한다. 금액상 제외된 경로의 전용 후보표는 만들지 않는다.",
        "- 주의: 아래 판단 재료만으로 계약 가능을 확정하지 말고, 확인된 법령/행정규칙 근거와 업체 데이터에 맞춰 제한적으로 표현한다.",
        "",
        "| 순위 | 경로 | 판단 | 법적 근거 | 실무 의미 |",
        "|---|---|---|---|---|",
    ]
    route_rank = 1
    for card in sorted(cards, key=_route_display_sort_key):
        if card.display_policy == "hide":
            continue
        priority = _format_route_display_priority(card, route_rank)
        if card.route_priority in {"primary", "secondary"}:
            route_rank += 1
        refs = ", ".join(card.legal_refs[:3]) or ", ".join(card.evidence_topics[:3])
        title = _format_route_display_title(card)
        judgment = _format_route_display_judgment(card)
        lines.append(f"| {priority} | {title} | {judgment} | {refs} | {card.practical_meaning} |")

    lines.extend([
        "",
        "답변 형식 지시:",
        "1. 판단요약에서 금액·계약대상·품목을 먼저 확정하고, 관련 조문 또는 행정규칙 근거를 함께 적어라.",
        "2. 바로 어려운 경로와 검토 가능한 대체 경로를 분리하라. 제외 경로는 길게 설명하지 말고 제외 이유만 쓴다.",
        "3. 구매경로 표나 문단에는 각 경로의 법적 근거를 생략하지 말고, 업체 후보표는 해당 경로의 근거 뒤에 붙인다.",
        "4. 물품은 2인 이상 견적, 종합쇼핑몰/MAS, 중소기업자간 경쟁제품·직접생산확인, 기술개발제품·혁신제품을 우선 검토한다.",
        "5. 용역은 2인 이상 견적, 지역제한, 평가요소, 면허·업종 기준 부산 용역업체 후보를 연결한다.",
        "6. 공사는 공종별 수의계약 한도, 지역제한, 공동도급, 지역업체 참여도/가점을 연결한다.",
        "7. 업체명은 '가능 업체'가 아니라 '검토 후보'로 표현하라.",
        "8. 마지막에 계약담당자가 바로 확인할 체크리스트를 붙여라.",
    ])
    return "\n".join(lines)
