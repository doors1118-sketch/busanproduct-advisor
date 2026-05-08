"""
지역업체 보호·우대제도 카탈로그.

라우터가 질문의 큰 유형을 잡은 뒤, 이 카탈로그가 "어떤 제도를 같이
검토해야 하는지"를 자동으로 펼친다. 최종 답변은 여기서 바로 만들지 않고,
조회 계획과 LLM 답변 지침을 제공한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Mapping


@dataclass(frozen=True)
class SupportScheme:
    id: str
    name: str
    contract_objects: tuple[str, ...]
    purpose: str
    agency_types: tuple[str, ...] = ()
    trigger_keywords: tuple[str, ...] = ()
    implicit_when_local_purchase: bool = False
    requires_amount: bool = False
    evidence_plan: tuple[dict, ...] = ()
    evidence_plan_by_agency: Mapping[str, tuple[dict, ...]] = field(default_factory=dict)
    answer_guidance: str = ""


@dataclass(frozen=True)
class CatalogMatch:
    scheme: SupportScheme
    reason: str
    score: int


def _plan(name: str, query: str, **extra) -> dict:
    item = {"name": name, "args": {"query": query}, "selected_reason": "regional_support_catalog"}
    item.update(extra)
    return item


def _agency_key(agency_type: str | None) -> str:
    raw = (agency_type or "default").strip()
    mapping = {
        "": "default",
        "default": "local_government",
        "local_government": "local_government",
        "local_gov": "local_government",
        "지방자치단체": "local_government",
        "부산광역시": "local_government",
        "부산시": "local_government",
        "national_agency": "national_agency",
        "central_government": "national_agency",
        "national_gov": "national_agency",
        "국가기관": "national_agency",
        "중앙부처": "national_agency",
        "public_corporation": "public_corporation",
        "public_enterprise": "public_corporation",
        "public_institution": "public_corporation",
        "public_agency": "public_corporation",
        "공기업": "public_corporation",
        "준정부기관": "public_corporation",
        "공공기관": "public_corporation",
        "invested_institution": "invested_institution",
        "busan_entity": "invested_institution",
        "지방공기업": "invested_institution",
        "출자출연기관": "invested_institution",
    }
    return mapping.get(raw, raw)


LOCAL_DIRECT_EVIDENCE = (
    _plan("search_law", "지방계약법 시행령 제25조 수의계약"),
    _plan("search_law", "지방계약법 시행령 제30조 수의계약 견적"),
    _plan("search_admin_rule", "지방자치단체 입찰 및 계약집행기준 수의계약 운영요령"),
)

NATIONAL_DIRECT_EVIDENCE = (
    _plan("search_law", "국가계약법 시행령 제26조 수의계약"),
    _plan("search_law", "국가계약법 시행령 제30조 견적"),
    _plan("search_admin_rule", "정부 입찰 계약 집행기준 수의계약"),
)

PUBLIC_DIRECT_EVIDENCE = (
    _plan("search_admin_rule", "공기업 준정부기관 계약사무규칙 수의계약"),
    _plan("search_law", "국가계약법 시행령 제26조 수의계약"),
    _plan("search_admin_rule", "기타공공기관 계약사무 운영규정 수의계약"),
)

LOCAL_POLICY_COMPANY_EVIDENCE = (
    _plan("search_law", "지방계약법 시행령 제25조 여성기업 장애인기업 사회적기업 수의계약"),
    _plan("search_law", "여성기업지원에 관한 법률"),
    _plan("search_law", "장애인기업활동 촉진법"),
    _plan("search_law", "사회적기업 육성법"),
)

NATIONAL_POLICY_COMPANY_EVIDENCE = (
    _plan("search_law", "국가계약법 시행령 제26조 여성기업 장애인기업 사회적기업 수의계약"),
    _plan("search_law", "여성기업지원에 관한 법률"),
    _plan("search_law", "장애인기업활동 촉진법"),
    _plan("search_law", "사회적기업 육성법"),
)

PUBLIC_POLICY_COMPANY_EVIDENCE = (
    _plan("search_admin_rule", "공기업 준정부기관 계약사무규칙 여성기업 장애인기업 사회적기업 수의계약"),
    _plan("search_law", "국가계약법 시행령 제26조 여성기업 장애인기업 사회적기업 수의계약"),
    _plan("search_law", "여성기업지원에 관한 법률"),
    _plan("search_law", "장애인기업활동 촉진법"),
    _plan("search_law", "사회적기업 육성법"),
)

LOCAL_REGIONAL_RESTRICTION_EVIDENCE = (
    _plan("search_law", "지방계약법 시행령 제20조 제한입찰"),
    _plan("search_law", "지방계약법 시행규칙 제24조 지역제한"),
    _plan("search_admin_rule", "지방자치단체 입찰 및 계약집행기준 지역제한"),
)

NATIONAL_REGIONAL_RESTRICTION_EVIDENCE = (
    _plan("search_law", "국가계약법 시행령 제21조 제한경쟁"),
    _plan("search_law", "국가계약법 시행규칙 지역제한 경쟁입찰"),
    _plan("search_admin_rule", "정부 입찰 계약 집행기준 지역제한"),
)

PUBLIC_REGIONAL_RESTRICTION_EVIDENCE = (
    _plan("search_admin_rule", "공기업 준정부기관 계약사무규칙 제한경쟁"),
    _plan("search_law", "국가계약법 시행령 제21조 제한경쟁"),
    _plan("search_admin_rule", "기타공공기관 계약사무 운영규정 제한경쟁"),
)

LOCAL_JOINT_CONTRACT_EVIDENCE = (
    _plan("chain_law_system", "지방계약법 공동계약 공동도급 지역업체 법령 행정규칙 체계"),
    _plan("search_law", "지방계약법 시행령 제88조 공동계약"),
    _plan("search_admin_rule", "지방자치단체 입찰 및 계약집행기준 공동계약 운영요령"),
)

NATIONAL_JOINT_CONTRACT_EVIDENCE = (
    _plan("chain_law_system", "국가계약법 공동계약 공동도급 지역업체 법령 행정규칙 체계"),
    _plan("search_law", "국가계약법 시행령 제72조 공동계약"),
    _plan("search_admin_rule", "공동계약운용요령 지역의무공동도급"),
)

PUBLIC_JOINT_CONTRACT_EVIDENCE = (
    _plan("search_admin_rule", "공기업 준정부기관 계약사무규칙 공동계약"),
    _plan("search_law", "국가계약법 시행령 제72조 공동계약"),
    _plan("search_admin_rule", "공동계약운용요령 지역의무공동도급"),
)

LOCAL_EVALUATION_EVIDENCE = (
    _plan("search_admin_rule", "지방자치단체 입찰시 낙찰자 결정기준 지역업체 가점"),
    _plan("search_admin_rule", "지방자치단체 입찰시 낙찰자 결정기준 적격심사"),
)

NATIONAL_EVALUATION_EVIDENCE = (
    _plan("search_admin_rule", "조달청 적격심사세부기준 지역업체 참여도"),
    _plan("search_admin_rule", "계약예규 적격심사기준 지역업체"),
)

PUBLIC_EVALUATION_EVIDENCE = (
    _plan("search_admin_rule", "공기업 준정부기관 계약사무규칙 낙찰자 결정"),
    _plan("search_admin_rule", "조달청 적격심사세부기준 지역업체 참여도"),
)


REGIONAL_SUPPORT_SCHEMES: tuple[SupportScheme, ...] = (
    SupportScheme(
        id="small_value_direct_contract",
        name="수의계약/소액수의/견적 방식",
        contract_objects=("goods", "service", "construction"),
        purpose="경쟁입찰 전 수의계약 가능성과 1인/2인 이상 견적 방식을 먼저 배제 또는 검토",
        trigger_keywords=("수의계약", "소액수의", "1인견적", "1인 견적", "2인견적", "견적", "바로 계약"),
        implicit_when_local_purchase=True,
        requires_amount=True,
        evidence_plan=LOCAL_DIRECT_EVIDENCE,
        evidence_plan_by_agency={
            "local_government": LOCAL_DIRECT_EVIDENCE,
            "invested_institution": LOCAL_DIRECT_EVIDENCE,
            "national_agency": NATIONAL_DIRECT_EVIDENCE,
            "public_corporation": PUBLIC_DIRECT_EVIDENCE,
        },
        answer_guidance="금액이 한도를 넘는 경로는 먼저 제외하고, 1인 견적과 2인 이상 견적을 분리해 설명한다.",
    ),
    SupportScheme(
        id="policy_company_direct_contract",
        name="정책기업 수의계약",
        contract_objects=("goods", "service"),
        purpose="여성기업·장애인기업·사회적기업 등 정책기업 경로를 통한 지역업체 활용 가능성 검토",
        trigger_keywords=("여성기업", "장애인기업", "사회적기업", "사회적협동조합", "자활기업", "마을기업", "정책기업"),
        implicit_when_local_purchase=True,
        requires_amount=True,
        evidence_plan=LOCAL_POLICY_COMPANY_EVIDENCE,
        evidence_plan_by_agency={
            "local_government": LOCAL_POLICY_COMPANY_EVIDENCE,
            "invested_institution": LOCAL_POLICY_COMPANY_EVIDENCE,
            "national_agency": NATIONAL_POLICY_COMPANY_EVIDENCE,
            "public_corporation": PUBLIC_POLICY_COMPANY_EVIDENCE,
        },
        answer_guidance="정책기업은 후보 자격이지 자동 계약 가능 사유가 아니므로 금액·견적 방식·인증 유효성을 함께 제시한다.",
    ),
    SupportScheme(
        id="regional_restriction_bid",
        name="지역제한경쟁입찰",
        contract_objects=("goods", "service", "construction"),
        purpose="수의계약이 어렵거나 경쟁입찰이 필요한 경우 부산 지역업체 참여 범위를 넓힘",
        trigger_keywords=("지역제한", "지역 제한", "제한경쟁", "지역업체", "부산업체", "관내업체", "부산 업체"),
        implicit_when_local_purchase=True,
        requires_amount=True,
        evidence_plan=LOCAL_REGIONAL_RESTRICTION_EVIDENCE,
        evidence_plan_by_agency={
            "local_government": LOCAL_REGIONAL_RESTRICTION_EVIDENCE,
            "invested_institution": LOCAL_REGIONAL_RESTRICTION_EVIDENCE,
            "national_agency": NATIONAL_REGIONAL_RESTRICTION_EVIDENCE,
            "public_corporation": PUBLIC_REGIONAL_RESTRICTION_EVIDENCE,
        },
        answer_guidance="수의계약이 어려우면 지역제한 가능 금액과 계약대상을 확인해 대체 경로로 제시한다.",
    ),
    SupportScheme(
        id="regional_joint_contract",
        name="지역의무공동도급/공동수급",
        contract_objects=("construction",),
        purpose="공사에서 지역업체 의무참여 또는 공동수급 구조를 통해 수주 참여 확대",
        trigger_keywords=("지역의무공동도급", "의무공동도급", "공동도급", "공동계약", "공동수급", "컨소시엄"),
        implicit_when_local_purchase=True,
        evidence_plan=LOCAL_JOINT_CONTRACT_EVIDENCE,
        evidence_plan_by_agency={
            "local_government": LOCAL_JOINT_CONTRACT_EVIDENCE,
            "invested_institution": LOCAL_JOINT_CONTRACT_EVIDENCE,
            "national_agency": NATIONAL_JOINT_CONTRACT_EVIDENCE,
            "public_corporation": PUBLIC_JOINT_CONTRACT_EVIDENCE,
        },
        answer_guidance="공사는 지역제한만 보지 말고 공동도급·공동수급 가능성과 지역업체 참여비율을 함께 검토한다.",
    ),
    SupportScheme(
        id="regional_company_evaluation_points",
        name="지역업체 참여도/가점/평가요소",
        contract_objects=("service", "construction"),
        purpose="낙찰자 결정방식에서 지역업체 참여도, 신인도, 평가항목을 통한 지역업체 우대 가능성 검토",
        trigger_keywords=("가점", "배점", "지역업체 참여도", "평가", "적격심사", "신인도", "제안서평가"),
        implicit_when_local_purchase=True,
        evidence_plan=LOCAL_EVALUATION_EVIDENCE,
        evidence_plan_by_agency={
            "local_government": LOCAL_EVALUATION_EVIDENCE,
            "invested_institution": LOCAL_EVALUATION_EVIDENCE,
            "national_agency": NATIONAL_EVALUATION_EVIDENCE,
            "public_corporation": PUBLIC_EVALUATION_EVIDENCE,
        },
        answer_guidance="용역·공사는 계약방식뿐 아니라 낙찰자 결정기준의 지역업체 참여도나 평가항목 반영 가능성을 제시한다.",
    ),
    SupportScheme(
        id="shopping_mall_mas_regional_factor",
        name="종합쇼핑몰/MAS 2단계 경쟁 지역요소",
        contract_objects=("goods",),
        purpose="종합쇼핑몰 등록 상품이면 MAS 2단계 경쟁 또는 납품요구 과정에서 지역업체 후보를 활용",
        trigger_keywords=("종합쇼핑몰", "쇼핑몰", "MAS", "다수공급자", "2단계 경쟁", "제3자단가", "나라장터"),
        implicit_when_local_purchase=True,
        evidence_plan=(
            _plan("search_admin_rule", "국가종합전자조달시스템 종합쇼핑몰 운영규정"),
            _plan("search_admin_rule", "물품 다수공급자계약 업무처리규정"),
            _plan("get_annexes", "물품 다수공급자계약 업무처리규정", args={"law_name": "물품 다수공급자계약 업무처리규정"}),
        ),
        answer_guidance="물품은 수의계약이 어려워도 쇼핑몰 등록 여부, 2단계 경쟁 대상 여부, 부산 공급업체 후보를 함께 확인한다.",
    ),
    SupportScheme(
        id="technology_development_priority_purchase",
        name="기술개발제품/우수조달/우선구매",
        contract_objects=("goods",),
        purpose="기술개발제품 13종, 우수조달물품 등 인증제품을 통한 우선구매·수의계약 가능성 검토",
        trigger_keywords=("기술개발제품", "성능인증", "NEP", "NET", "우수조달", "우수발명", "녹색기술", "GS인증", "우선구매"),
        implicit_when_local_purchase=True,
        evidence_plan=(
            _plan("search_law", "중소기업제품 구매촉진 및 판로지원법 제13조 기술개발제품"),
            _plan("search_law", "중소기업제품 구매촉진 및 판로지원법 제14조 우선구매"),
            _plan("search_law", "조달사업법 제9조의2 우수조달물품"),
        ),
        answer_guidance="인증제품은 제품명·인증유효성·구매품목 일치가 확인될 때만 후보 경로로 제시한다.",
    ),
    SupportScheme(
        id="innovation_product_purchase",
        name="혁신제품/혁신시제품 구매",
        contract_objects=("goods",),
        purpose="혁신제품·혁신시제품 지정 상품을 통한 특례 구매 가능성 검토",
        trigger_keywords=("혁신제품", "혁신시제품", "혁신장터", "시범구매"),
        implicit_when_local_purchase=True,
        evidence_plan=(
            _plan("search_admin_rule", "혁신제품 구매 운영 규정"),
            _plan("search_admin_rule", "혁신제품 시범구매계약 추가특수조건"),
        ),
        answer_guidance="혁신제품은 지정 상태, 혁신장터 등록, 조달청 계약 여부를 확인사항으로 붙인다.",
    ),
    SupportScheme(
        id="sme_competition_direct_production",
        name="중소기업자간 경쟁제품/직접생산확인",
        contract_objects=("goods",),
        purpose="중소기업자간 경쟁제품이면 직접생산확인과 세부품명 기준을 확인해 지역업체 후보 적격성 검토",
        trigger_keywords=("중소기업자간", "중기간", "중소기업경쟁제품", "직접생산", "직생", "세부품명"),
        implicit_when_local_purchase=True,
        evidence_plan=(
            _plan("search_law", "중소기업제품 구매촉진 및 판로지원법 제6조 중소기업자간 경쟁제품"),
            _plan("search_law", "중소기업제품 구매촉진 및 판로지원법 시행령 제13조 직접생산"),
            _plan("search_admin_rule", "조달청 제조물품 직접생산확인 기준"),
        ),
        answer_guidance="세부품명과 직접생산확인 대상 여부를 업체 후보의 필수 확인사항으로 제시한다.",
    ),
)


def _compact(text: str) -> str:
    return re.sub(r"[\sㆍ·_-]+", "", (text or "").lower())


def _has_any(text: str, words: tuple[str, ...]) -> bool:
    compact = _compact(text)
    return any(_compact(word) in compact for word in words)


def infer_contract_object(user_message: str, default: str = "goods") -> str:
    q = user_message or ""
    if any(term in q for term in ("용역", "위탁", "유지관리", "청소", "경비", "설계", "감리", "컨설팅", "엔지니어링")):
        return "service"
    if any(term in q for term in ("공사", "시공", "건축", "토목", "전기공사", "소방공사", "정보통신공사")):
        return "construction"
    return default


def has_amount(user_message: str) -> bool:
    return bool(re.search(r"\d+\s*(억|억원|천만|천만원|백만|백만원|만|만원)|\d{5,}\s*원", user_message or ""))


def has_local_purchase_intent(user_message: str) -> bool:
    return _has_any(
        user_message,
        (
            "지역업체", "부산업체", "부산 업체", "지역상품", "부산상품", "관내업체",
            "지역제한", "지역 업체", "지역 우대", "부산", "수주", "활용",
        ),
    )


def match_regional_support_catalog(
    user_message: str,
    *,
    contract_object: str | None = None,
    agency_type: str | None = None,
    max_matches: int = 8,
) -> list[CatalogMatch]:
    """질문 조건에 맞는 지역업체 보호·우대제도 후보를 반환한다."""
    object_type = contract_object or infer_contract_object(user_message)
    agency = _agency_key(agency_type)
    local_intent = has_local_purchase_intent(user_message)
    amount_present = has_amount(user_message)
    matches: list[CatalogMatch] = []

    for scheme in REGIONAL_SUPPORT_SCHEMES:
        if object_type not in scheme.contract_objects:
            continue
        if scheme.agency_types and agency not in scheme.agency_types:
            continue

        explicit = _has_any(user_message, scheme.trigger_keywords)
        implicit = local_intent and scheme.implicit_when_local_purchase
        if not explicit and not implicit:
            continue

        score = 80 if explicit else 50
        if local_intent:
            score += 10
        if amount_present:
            score += 5
        if scheme.requires_amount and not amount_present:
            score -= 15

        reason = "explicit_keyword" if explicit else "implicit_local_purchase_support"
        matches.append(CatalogMatch(scheme=scheme, reason=reason, score=score))

    matches.sort(key=lambda m: (-m.score, m.scheme.id))
    return matches[:max_matches]


def build_catalog_evidence_plan(
    user_message: str,
    *,
    contract_object: str | None = None,
    agency_type: str | None = None,
    max_items: int = 20,
) -> list[dict]:
    """카탈로그 매칭 결과를 MCP-compatible 조회 계획으로 변환한다."""
    matches = match_regional_support_catalog(
        user_message,
        contract_object=contract_object,
        agency_type=agency_type,
    )
    plan: list[dict] = []
    seen: set[str] = set()
    agency = _agency_key(agency_type)
    for match in matches:
        evidence_plan = (
            match.scheme.evidence_plan_by_agency.get(agency)
            or match.scheme.evidence_plan_by_agency.get("local_government")
            or match.scheme.evidence_plan
        )
        for item in evidence_plan:
            cloned = {
                "name": item["name"],
                "args": dict(item.get("args") or {}),
                "selected_reason": f"regional_support_catalog:{match.scheme.id}",
                "catalog_scheme_id": match.scheme.id,
                "catalog_scheme_name": match.scheme.name,
                "catalog_match_reason": match.reason,
                "catalog_agency_type": agency,
            }
            key_value = (
                cloned["args"].get("query")
                or cloned["args"].get("law_name")
                or cloned["args"].get("mst")
                or ""
            )
            key = f"{cloned['name']}:{key_value}"
            if key in seen:
                continue
            seen.add(key)
            plan.append(cloned)
            if len(plan) >= max_items:
                return plan
    return plan


def format_catalog_matches_for_llm(
    user_message: str,
    *,
    contract_object: str | None = None,
    agency_type: str | None = None,
) -> str:
    matches = match_regional_support_catalog(
        user_message,
        contract_object=contract_object,
        agency_type=agency_type,
    )
    if not matches:
        return ""
    agency = _agency_key(agency_type)

    lines = [
        "",
        "[지역업체 보호·우대제도 카탈로그 매칭]",
        "- 아래 제도는 질문 조건에서 자동으로 검토 대상으로 선택된 항목이다.",
        f"- 적용 기관유형: {agency}",
        "- 답변에서는 사용자가 제도를 직접 언급하지 않았더라도, 적용 가능성이 있으면 실무 대안으로 설명한다.",
        "",
        "| 제도 | 선택 이유 | 적용 기관유형 | 답변에서 다룰 포인트 |",
        "|---|---|---|---|",
    ]
    for match in matches:
        lines.append(
            f"| {match.scheme.name} | {match.reason} | {agency} | {match.scheme.answer_guidance} |"
        )
    return "\n".join(lines)
