"""
Conservative front gateway for procurement chatbot routing.

The gateway does not try to understand every question. It only short-circuits
questions that are clear enough to handle before the expensive router/tier flow.
Ambiguous or case-specific questions must pass through to the existing router.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
import re


GatewayRoute = Literal[
    "standard_card",
    "direct_article",
    "company_search",
    "complex_router",
]


@dataclass(frozen=True)
class GatewayDecision:
    route: GatewayRoute
    confidence: Literal["certain", "ambiguous"] = "certain"
    reason: str = ""
    matched_card_id: str | None = None
    exclusions: list[str] = field(default_factory=list)
    llm_validation_required: bool = False
    law_query: str | None = None


_LAW_PATTERNS = [
    "지방자치단체를당사자로하는계약에관한법률시행령",
    "지방자치단체를당사자로하는계약에관한법률시행규칙",
    "지방자치단체를당사자로하는계약에관한법률",
    "국가를당사자로하는계약에관한법률시행령",
    "국가를당사자로하는계약에관한법률시행규칙",
    "국가를당사자로하는계약에관한법률",
    "공기업ㆍ준정부기관계약사무규칙",
    "공기업및준정부기관계약사무규칙",
    "지방계약법시행령",
    "지방계약법시행규칙",
    "지방계약법",
    "국가계약법시행령",
    "국가계약법시행규칙",
    "국가계약법",
    "조달사업법시행령",
    "조달사업법",
    "중소기업구매촉진법시행령",
    "중소기업구매촉진법",
]

_LAW_NORMALIZE = {
    "지방자치단체를당사자로하는계약에관한법률시행령": "지방계약법 시행령",
    "지방자치단체를당사자로하는계약에관한법률시행규칙": "지방계약법 시행규칙",
    "지방자치단체를당사자로하는계약에관한법률": "지방계약법",
    "국가를당사자로하는계약에관한법률시행령": "국가계약법 시행령",
    "국가를당사자로하는계약에관한법률시행규칙": "국가계약법 시행규칙",
    "국가를당사자로하는계약에관한법률": "국가계약법",
    "공기업ㆍ준정부기관계약사무규칙": "공기업계약사무규칙",
    "공기업및준정부기관계약사무규칙": "공기업계약사무규칙",
    "지방계약법시행령": "지방계약법 시행령",
    "지방계약법시행규칙": "지방계약법 시행규칙",
    "지방계약법": "지방계약법",
    "국가계약법시행령": "국가계약법 시행령",
    "국가계약법시행규칙": "국가계약법 시행규칙",
    "국가계약법": "국가계약법",
    "조달사업법시행령": "조달사업법 시행령",
    "조달사업법": "조달사업법",
    "중소기업구매촉진법시행령": "중소기업구매촉진법 시행령",
    "중소기업구매촉진법": "중소기업구매촉진법",
}


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


def _has_amount(q: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?(?:억|천만|백만|만원|원)", q))


def _has_contract_object(q: str) -> bool:
    return any(term in q for term in (
        "물품", "용역", "공사", "구매", "납품", "제조", "제품", "사려", "살건데", "구입",
    ))


def _has_case_judgment(q: str) -> bool:
    return any(term in q for term in (
        "가능", "되나", "될까", "해도", "할수", "살건데", "사려", "진행", "계약해도",
    ))


def _has_contract_method(q: str) -> bool:
    return any(term in q for term in (
        "수의계약", "수의", "1인견적", "2인견적", "견적", "입찰", "지역제한", "공동도급",
    ))


def _is_case_specific(q: str) -> bool:
    return _has_amount(q) and _has_contract_object(q) and (_has_case_judgment(q) or _has_contract_method(q))


def _extract_direct_article_query(q_original: str) -> str | None:
    q = q_original.replace(" ", "")
    article_match = re.search(r"제\d+조(?:의\d+)?", q)
    if not article_match:
        return None

    for law_pattern in sorted(_LAW_PATTERNS, key=len, reverse=True):
        if law_pattern in q:
            return f"{_LAW_NORMALIZE.get(law_pattern, law_pattern)} {article_match.group(0)}"
    return None


def _has_specific_item(q_original: str) -> bool:
    q = _compact(q_original)
    if any(term in q for term in (
        "led", "엘이디", "엘이디등", "엘이디조명", "led등", "led조명",
        "cctv", "씨씨티비", "영상감시장치",
        "컴퓨터", "프린터", "복사기", "에어컨", "냉난방", "가구", "의자", "책상", "차량", "서버", "조명",
        "청소", "경비", "소프트웨어",
    )):
        return True
    # "물품" and "제품" are contract/object classes, not specific item names.
    return False


def _requests_company_lookup(q: str) -> bool:
    return any(term in q for term in (
        "부산업체", "지역업체", "업체추천", "업체후보", "업체있", "업체알려", "후보", "추천", "찾아", "검색",
    ))


def _standard_card_id(q: str) -> str | None:
    if (
        ("지역제한" in q or "지역제한경쟁" in q)
        and ("종합공사" in q or "건설공사" in q)
        and any(term in q for term in ("기준", "금액", "얼마", "몇억", "88억", "100억", "150억"))
    ):
        return "regional_restriction_construction_threshold"

    if (
        "수의계약" in q
        and any(term in q for term in ("기준", "한도", "금액", "얼마", "1인견적", "견적"))
    ):
        return "sole_contract_threshold"

    if (
        ("지역업체" in q or "지역기업" in q)
        and any(term in q for term in ("가점", "점수", "참여도", "신인도", "적격심사", "평가"))
    ):
        return "local_company_point"

    if (
        ("지역의무" in q or "의무공동" in q or ("공동도급" in q and "지역" in q))
        and any(term in q for term in ("기준", "비율", "몇", "가능", "공사", "발주", "공동도급"))
    ):
        return "regional_mandatory_joint_contract"

    return None


def decide_query_gateway(user_message: str) -> GatewayDecision:
    q = _compact(user_message)
    exclusions: list[str] = []

    if _is_case_specific(q):
        exclusions.append("amount_case_question")

    direct_article_query = _extract_direct_article_query(user_message)
    if direct_article_query and not exclusions:
        return GatewayDecision(
            route="direct_article",
            reason="law_name_and_article_detected",
            law_query=direct_article_query,
        )

    card_id = _standard_card_id(q)
    if card_id and not exclusions:
        return GatewayDecision(
            route="standard_card",
            reason="certain_standard_card_match",
            matched_card_id=card_id,
        )

    if card_id and exclusions:
        return GatewayDecision(
            route="complex_router",
            confidence="ambiguous",
            reason="standard_card_candidate_but_case_specific",
            matched_card_id=card_id,
            exclusions=exclusions,
            llm_validation_required=True,
        )

    if _requests_company_lookup(q) and _has_specific_item(user_message) and not _has_amount(q):
        return GatewayDecision(
            route="company_search",
            reason="specific_item_company_lookup_without_amount_case",
        )

    return GatewayDecision(
        route="complex_router",
        confidence="ambiguous",
        reason="no_certain_front_gate_match",
        exclusions=exclusions,
        llm_validation_required=True,
    )
