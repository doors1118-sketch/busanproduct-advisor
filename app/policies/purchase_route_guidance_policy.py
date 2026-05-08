"""
구매경로 판단 재료 생성 정책.

이 모듈은 최종 답변을 만들지 않는다. 금액·품목·업체검색 결과를 바탕으로
LLM이 실무형 답변을 작성할 때 참고할 "경로별 판단 재료"를 구조화한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

try:
    from policies.numeric_basis_policy import compare_amount, get_numeric_display
except ImportError:
    from app.policies.numeric_basis_policy import compare_amount, get_numeric_display


@dataclass(frozen=True)
class PurchaseRouteCard:
    route_id: str
    title: str
    status: str
    user_label: str
    practical_meaning: str
    required_checks: list[str]
    evidence_topics: list[str]


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


def _tool_counts(tool_results: list[dict] | None) -> dict[str, int | None]:
    counts: dict[str, int | None] = {
        "shopping_mall": None,
        "local_company": None,
        "local_license_company": None,
        "policy_company": None,
        "certified_product": None,
        "innovation_product": None,
    }
    for row in tool_results or []:
        name = row.get("tool_name", "")
        count = _count_from_result_text(row.get("result", ""))
        if "shopping_mall" in name:
            counts["shopping_mall"] = max(counts["shopping_mall"] or 0, count or 0)
        elif "company_by_license" in name:
            counts["local_license_company"] = max(counts["local_license_company"] or 0, count or 0)
            counts["local_company"] = max(counts["local_company"] or 0, count or 0)
        elif "local_company" in name:
            counts["local_company"] = max(counts["local_company"] or 0, count or 0)
        elif "company_by_policy" in name:
            counts["policy_company"] = (counts["policy_company"] or 0) + (count or 0)
        elif "certified_product" in name:
            counts["certified_product"] = max(counts["certified_product"] or 0, count or 0)
        elif "innovation_product" in name:
            counts["innovation_product"] = max(counts["innovation_product"] or 0, count or 0)
    return counts


def _candidate_status(count: int | None) -> tuple[str, str]:
    if count is None:
        return "needs_lookup", "조회 필요"
    if count > 0:
        return "candidate_found", f"후보 {count}건"
    return "no_candidate_found", "후보 미확인"


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
    counts = _tool_counts(tool_results)

    if object_type == "service":
        return _build_service_route_cards(amount, item_name, counts)
    if object_type == "construction":
        return _build_construction_route_cards(amount, item_name, counts)

    general_status = "needs_amount_check"
    general_label = "금액 확인 필요"
    general_meaning = "일반 소액 수의계약 가능 여부는 추정가격 기준 금액과 견적 방식 확인이 필요합니다."
    general_ref = "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD"
    general_threshold = get_numeric_display(general_ref)
    general_compare = compare_amount(amount, general_ref)
    if general_compare == "above":
        general_status = "not_viable"
        general_label = f"일반 {general_threshold} 소액수의 경로는 어려움"
        general_meaning = f"질문 금액은 내부 source map의 일반 소액수의 기준({general_threshold})을 초과하므로 일반적인 1인 견적 소액수의 경로로 바로 처리하기 어렵습니다."
    elif general_compare == "below_or_equal":
        general_status = "viable_check"
        general_label = "일반 소액수의 검토 가능"
        general_meaning = f"내부 source map 기준({general_threshold}) 이하라면 일반 소액수의 및 견적 방식 검토 대상입니다."

    policy_1p_status = "needs_amount_check"
    policy_1p_label = "금액 확인 필요"
    policy_1p_meaning = "정책기업 경로는 기업유형, 추정가격, 1인/2인 이상 견적 방식을 분리해 봐야 합니다."
    policy_ref = "P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD"
    policy_threshold = get_numeric_display(policy_ref)
    policy_compare = compare_amount(amount, policy_ref)
    if policy_compare == "above":
        policy_1p_status = "not_viable"
        policy_1p_label = f"{policy_threshold} 1인 견적 경로는 어려움"
        policy_1p_meaning = f"여성기업·장애인기업·사회적기업 등 정책기업이라도 내부 source map의 1인 견적 기준({policy_threshold})을 초과하면 해당 경로로 바로 처리하기 어렵습니다. 다만 정책기업 관련 다른 수의계약/견적 경로는 별도 검토가 필요합니다."
    elif policy_compare == "below_or_equal":
        policy_1p_status = "viable_check"
        policy_1p_label = "정책기업 1인 견적 검토 가능"
        policy_1p_meaning = f"내부 source map 기준({policy_threshold}) 이하라면 정책기업 1인 견적 가능성을 검토할 수 있습니다."

    shopping_status, shopping_label = _candidate_status(counts["shopping_mall"])
    cert_status, cert_label = _candidate_status(counts["certified_product"])
    innovation_status, innovation_label = _candidate_status(counts["innovation_product"])
    local_status, local_label = _candidate_status(counts["local_company"])

    return [
        PurchaseRouteCard(
            route_id="general_small_value_direct",
            title="일반 물품 소액수의",
            status=general_status,
            user_label=general_label,
            practical_meaning=general_meaning,
            required_checks=["추정가격/부가세 포함 여부", "1인 견적 또는 2인 이상 견적", "기관유형별 적용 기준"],
            evidence_topics=["지방계약법 시행령 수의계약", "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령"],
        ),
        PurchaseRouteCard(
            route_id="policy_company_one_quote",
            title="정책기업 1인 견적",
            status=policy_1p_status,
            user_label=policy_1p_label,
            practical_meaning=policy_1p_meaning,
            required_checks=["정책기업 유형", "인증서 유효기간", "견적 방식", "기관유형별 한도"],
            evidence_topics=["여성기업지원법", "장애인기업활동 촉진법", "사회적기업 육성법", "수의계약 운영요령"],
        ),
        PurchaseRouteCard(
            route_id="shopping_mall_mas",
            title="종합쇼핑몰/MAS",
            status=shopping_status,
            user_label=shopping_label,
            practical_meaning="종합쇼핑몰에 해당 품목이 등록되어 있으면 납품요구, MAS 2단계 경쟁 등 쇼핑몰 경로를 우선 검토할 수 있습니다.",
            required_checks=["쇼핑몰 계약상태", "납품 가능 지역", "규격 일치", "2단계 경쟁 대상 여부"],
            evidence_topics=["나라장터 종합쇼핑몰 운영규정", "물품 다수공급자계약 업무처리규정"],
        ),
        PurchaseRouteCard(
            route_id="innovation_product",
            title="혁신제품/혁신시제품",
            status=innovation_status,
            user_label=innovation_label,
            practical_meaning="혁신제품 또는 혁신시제품 후보가 있으면 지정 유효기간과 제품 일치 여부를 확인한 뒤 수의계약 특례 가능성을 검토합니다.",
            required_checks=["혁신제품 지정 유효기간", "혁신장터 등록 여부", "구매 품목과 지정 제품의 일치", "수요기관 적용 법령"],
            evidence_topics=["혁신제품 구매 운영 규정", "혁신제품 시범구매계약 추가특수조건"],
        ),
        PurchaseRouteCard(
            route_id="technology_development_product",
            title="기술개발제품/우수조달 등 인증제품",
            status=cert_status,
            user_label=cert_label,
            practical_meaning="성능인증, NEP, NET, 우수조달물품 등 인증제품 후보가 있으면 우선구매 또는 수의계약 가능성을 검토합니다.",
            required_checks=["인증 유형", "인증 유효기간", "인증제품명과 구매품목 일치", "조달등록 또는 쇼핑몰 등록 여부"],
            evidence_topics=["중소기업제품 구매촉진 및 판로지원법", "중소기업제품 구매촉진법 시행령", "우수조달물품 지정관리 규정"],
        ),
        PurchaseRouteCard(
            route_id="local_company_competitive",
            title="부산 지역업체 경쟁/후보 발굴",
            status=local_status,
            user_label=local_label,
            practical_meaning="수의계약이 곧바로 어렵다면 부산 조달등록 업체를 후보로 놓고 지역제한, 평가요소, 쇼핑몰 경로를 함께 검토합니다.",
            required_checks=["부산 소재 여부", "조달등록/영업상태", "직접생산확인", "면허·업종·규격 적합성"],
            evidence_topics=["지역제한 입찰", "지역업체 정의", "직접생산확인 기준"],
        ),
    ]


def _build_service_route_cards(amount: int | None, item_name: str, counts: dict[str, int | None]) -> list[PurchaseRouteCard]:
    general_status = "needs_amount_check"
    general_label = "금액·견적 방식 확인 필요"
    general_meaning = "용역 수의계약은 추정가격, 1인/2인 이상 견적, 용역 종류에 따라 가능 범위가 달라집니다."
    general_ref = "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD"
    general_threshold = get_numeric_display(general_ref)
    general_compare = compare_amount(amount, general_ref)
    if general_compare == "above":
        general_status = "not_viable"
        general_label = f"일반 {general_threshold} 소액수의 경로는 어려움"
        general_meaning = f"내부 source map의 일반 소액수의 기준({general_threshold})을 초과하는 용역은 일반적인 1인 견적 소액수의 경로로 바로 처리하기 어렵고, 2인 이상 견적·경쟁입찰·특례 여부를 나눠 봐야 합니다."
    elif general_compare == "below_or_equal":
        general_status = "viable_check"
        general_label = "일반 소액수의 검토 가능"

    policy_status = "needs_amount_check"
    policy_label = "정책기업 경로 확인 필요"
    policy_meaning = "여성기업·장애인기업·사회적기업 등 정책기업 경로는 용역에도 검토될 수 있으나, 금액과 견적 방식 확인이 필요합니다."
    policy_ref = "P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD"
    policy_threshold = get_numeric_display(policy_ref)
    policy_compare = compare_amount(amount, policy_ref)
    if policy_compare == "above":
        policy_status = "not_viable"
        policy_label = f"{policy_threshold} 1인 견적 경로는 어려움"
        policy_meaning = f"정책기업이라도 내부 source map의 1인 견적 기준({policy_threshold})을 초과하면 해당 경로로는 처리하기 어렵고, 2인 이상 견적이나 경쟁 방식 전환을 검토해야 합니다."
    elif policy_compare == "below_or_equal":
        policy_status = "viable_check"
        policy_label = "정책기업 1인 견적 검토 가능"

    local_status, local_label = _candidate_status(counts.get("local_license_company") or counts.get("local_company"))
    policy_candidate_status, policy_candidate_label = _candidate_status(counts.get("policy_company"))

    return [
        PurchaseRouteCard(
            route_id="service_small_value_direct",
            title="일반 용역 소액수의",
            status=general_status,
            user_label=general_label,
            practical_meaning=general_meaning,
            required_checks=["추정가격/부가세 포함 여부", "1인 견적 또는 2인 이상 견적", "용역 종류", "기관유형별 기준"],
            evidence_topics=["지방계약법 시행령 수의계약", "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령"],
        ),
        PurchaseRouteCard(
            route_id="service_policy_company",
            title="정책기업 용역 수의계약",
            status=policy_status,
            user_label=policy_label,
            practical_meaning=policy_meaning,
            required_checks=["정책기업 유형", "인증 유효기간", "용역 수행 가능 업종", "견적 방식"],
            evidence_topics=["여성기업지원법", "장애인기업활동 촉진법", "사회적기업 육성법", "수의계약 운영요령"],
        ),
        PurchaseRouteCard(
            route_id="service_regional_restriction",
            title="지역제한/지역업체 참여 용역",
            status="viable_check",
            user_label="조건부 검토",
            practical_meaning="수의계약이 어렵다면 용역 특성과 금액에 맞춰 지역제한, 참가자격, 평가요소를 통해 부산 업체 참여 가능성을 검토합니다.",
            required_checks=["지역제한 가능 금액", "업종·면허 제한 가능성", "과업 범위", "평가항목 반영 가능성"],
            evidence_topics=["지역제한 입찰", "용역 적격심사", "지방자치단체 입찰 및 계약집행기준"],
        ),
        PurchaseRouteCard(
            route_id="local_service_company",
            title="부산 용역업체 후보",
            status=local_status,
            user_label=local_label,
            practical_meaning="과업명 또는 면허·업종으로 부산 업체 후보를 찾고, 실제 수행능력과 면허를 확인합니다.",
            required_checks=["부산 소재 여부", "해당 용역 면허·업종", "실적·인력·장비", "영업상태"],
            evidence_topics=["지역업체 정의", "입찰참가자격", "용역 수행능력 평가"],
        ),
        PurchaseRouteCard(
            route_id="service_policy_candidate",
            title="정책기업 용역 후보",
            status=policy_candidate_status,
            user_label=policy_candidate_label,
            practical_meaning="정책기업 후보가 있으면 용역 수행 업종과 정책기업 지위를 함께 확인해 구매전략에 반영합니다.",
            required_checks=["정책기업 지위", "용역 수행 업종", "인증 유효기간", "견적 방식"],
            evidence_topics=["정책기업 수의계약", "수의계약 운영요령"],
        ),
    ]


def _build_construction_route_cards(amount: int | None, item_name: str, counts: dict[str, int | None]) -> list[PurchaseRouteCard]:
    direct_status = "needs_amount_check"
    direct_label = "금액·공종 확인 필요"
    direct_meaning = "공사는 공종, 추정가격, 전문/종합 여부에 따라 수의계약·지역제한·공동도급 검토 방식이 달라집니다."
    general_ref = "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD"
    general_threshold = get_numeric_display(general_ref)
    general_compare = compare_amount(amount, general_ref)
    if general_compare == "above":
        direct_status = "not_viable"
        direct_label = "일반 소액수의 경로는 보수적 검토 필요"
        direct_meaning = f"내부 source map의 일반 소액수의 기준({general_threshold})을 초과하는 공사는 일반 소액수의로 바로 단정하기 어렵고, 공종별 한도와 예외사유를 확인해야 합니다."
    elif general_compare == "below_or_equal":
        direct_status = "viable_check"
        direct_label = "소액수의 검토 가능"

    local_status, local_label = _candidate_status(counts.get("local_license_company") or counts.get("local_company"))

    return [
        PurchaseRouteCard(
            route_id="construction_direct_contract",
            title="공사 수의계약",
            status=direct_status,
            user_label=direct_label,
            practical_meaning=direct_meaning,
            required_checks=["추정가격", "종합/전문공사 구분", "공종", "예외적 수의계약 사유"],
            evidence_topics=["지방계약법 시행령 수의계약", "수의계약 운영요령"],
        ),
        PurchaseRouteCard(
            route_id="construction_regional_restriction",
            title="공사 지역제한 입찰",
            status="viable_check",
            user_label="조건부 검토",
            practical_meaning="금액과 공종이 기준에 맞으면 부산 지역업체로 참가자격을 제한하는 방안을 검토할 수 있습니다.",
            required_checks=["종합/전문공사 구분", "지역제한 기준금액", "공사현장 소재지", "면허 요건"],
            evidence_topics=["지방계약법 시행규칙 제24조", "지역제한 입찰 기준"],
        ),
        PurchaseRouteCard(
            route_id="construction_joint_contract",
            title="지역의무공동도급/공동수급",
            status="viable_check",
            user_label="조건부 검토",
            practical_meaning="대형 공사나 공동계약이 가능한 사안이면 지역업체 의무참여 또는 공동수급 구조를 검토합니다.",
            required_checks=["공동계약 허용 여부", "지역업체 참여비율", "공종 분담 가능성", "발주기관 기준"],
            evidence_topics=["공동계약 운영요령", "지역의무공동도급"],
        ),
        PurchaseRouteCard(
            route_id="construction_local_company_points",
            title="지역업체 참여도/가점",
            status="viable_check",
            user_label="조건부 검토",
            practical_meaning="적격심사·종합평가 등에서 지역업체 참여도나 신인도 요소를 반영할 수 있는지 확인합니다.",
            required_checks=["낙찰자 결정방식", "평가기준", "지역업체 인정 기준", "공고문 반영 가능성"],
            evidence_topics=["지방자치단체 입찰시 낙찰자 결정기준", "지역업체 참여도"],
        ),
        PurchaseRouteCard(
            route_id="local_construction_company",
            title="부산 공사업체 후보",
            status=local_status,
            user_label=local_label,
            practical_meaning="공종·면허 기준으로 부산 업체 후보를 찾고, 면허·시공능력·실적을 확인합니다.",
            required_checks=["부산 소재 여부", "공사업 면허", "시공능력/실적", "영업상태"],
            evidence_topics=["지역업체 정의", "입찰참가자격", "공사업 면허"],
        ),
    ]


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
    agency_label = agency_type or "미지정"
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
        "- 작성 원칙: 불가 경로는 명확히 제외하고, 조건부 경로는 필요한 확인사항과 업체 후보를 연결한다.",
        "- 주의: 아래 판단 재료만으로 계약 가능을 확정하지 말고, 확인된 법령/행정규칙 근거와 업체 데이터에 맞춰 제한적으로 표현한다.",
        "",
        "| 경로 | 현재 판단 | 실무 의미 | 답변에 연결할 근거 주제 |",
        "|---|---|---|---|",
    ]
    for card in cards:
        topics = ", ".join(card.evidence_topics[:3])
        lines.append(f"| {card.title} | {card.user_label} | {card.practical_meaning} | {topics} |")

    lines.extend([
        "",
        "답변 형식 지시:",
        "1. 먼저 '이 금액에서 바로 어려운 경로'와 '검토 가능한 대체 경로'를 나눠라.",
        "2. 물품은 종합쇼핑몰·혁신제품·기술개발제품·부산 조달등록 업체 후보를 경로별로 묶어라.",
        "3. 용역은 과업명/면허/업종 기준 부산 용역업체 후보와 정책기업 후보를 연결하라.",
        "4. 공사는 공종/면허 기준 부산 공사업체 후보와 지역제한·공동도급·지역업체 가점 경로를 연결하라.",
        "5. 업체명은 '가능 업체'가 아니라 '검토 후보'로 표현하라.",
        "6. 마지막에 계약담당자가 바로 확인할 체크리스트를 붙여라.",
    ])
    return "\n".join(lines)
