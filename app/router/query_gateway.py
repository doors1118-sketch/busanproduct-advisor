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

try:
    from app.router.intent_normalization import normalize_query_intent
except Exception:  # Runtime path when app/ is on sys.path.
    from router.intent_normalization import normalize_query_intent


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
    return normalize_query_intent(q).amount is not None or bool(re.search(r"\d+(?:\.\d+)?(?:억|천만|백만|만원|원)", q))


def _has_contract_object(q: str) -> bool:
    if normalize_query_intent(q).contract_object:
        return True
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
    if normalize_query_intent(q_original).item_name:
        return True
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
    norm = normalize_query_intent(q)
    if norm.company_lookup_blocked:
        return False
    if norm.company_lookup_requested:
        return True
    return any(term in q for term in (
        "업체추천", "업체후보", "업체있", "업체알려", "후보", "추천", "찾아", "검색",
    ))


def _is_pure_company_lookup_request(q_original: str) -> bool:
    """Gateway fast-exit is allowed only for a narrow supplier-candidate ask."""
    norm = normalize_query_intent(q_original)
    q = _compact(q_original)
    if norm.company_lookup_blocked or not norm.company_lookup_requested:
        return False
    if not _has_specific_item(q_original):
        return False
    if _has_amount(q):
        return False

    # "절차 말고 업체 후보만"처럼 사용자가 후보표만 원한다고 명시한 경우.
    if norm.company_lookup_only:
        return True

    hard_lookup = any(term in q for term in (
        "업체추천", "기업추천", "후보추천", "업체후보", "기업후보",
        "업체목록", "기업목록", "업체리스트", "기업리스트", "업체명",
        "찾아", "검색", "조회", "보여",
    ))
    if not hard_lookup:
        return False

    route_or_judgment_terms = (
        "계약방법", "구매방법", "활용방법", "활용방안", "참여방법",
        "경로", "가능", "고를수", "살수", "사면", "수의", "입찰",
        "견적", "종합쇼핑몰", "mas", "다수공급자", "지역제한", "가점",
        "공동도급", "절차", "프로세스", "근거", "기준", "검토", "우대",
    )
    if any(term in q for term in route_or_judgment_terms):
        return False

    return True


def _has_agency_law_conflict(q: str) -> bool:
    has_national_or_public = any(term in q for term in ("국가기관", "국가계약", "공기업", "준정부", "공공기관"))
    has_local_law = any(term in q for term in ("지방계약", "지방자치단체", "지자체"))
    has_conflict_ask = any(term in q for term in ("그대로", "다르", "안되", "안되지", "혼동", "기준", "우대", "지역제한"))
    return has_national_or_public and has_local_law and has_conflict_ask


def _has_procurement_design_question(q: str) -> bool:
    has_design_term = any(term in q for term in ("지역제한", "평가항목", "면허", "참가자격", "부당제한", "규격서"))
    has_how = any(term in q for term in ("어떻게", "검토", "설계", "조심", "확인"))
    return has_design_term and has_how


def _is_vat_threshold_basis_question(q: str) -> bool:
    compact = re.sub(r"\s+", "", q).lower()
    has_vat = any(term in compact for term in ("부가가치세", "부가세", "vat"))
    has_basis_intent = any(
        term in compact
        for term in ("포함", "제외", "빼", "산입", "계산", "기준", "추정가격", "예정가격")
    )
    has_contract_intent = any(
        term in compact
        for term in ("수의계약", "1인견적", "견적", "계약한도", "한도")
    )
    return has_vat and has_basis_intent and has_contract_intent


def _is_innovation_or_certified_product_contract_question(q: str) -> bool:
    has_product_status = any(
        term in q
        for term in ("혁신제품", "혁신시제품", "혁신장터", "기술개발제품", "우수조달", "성능인증", "gs인증", "nep", "net")
    )
    has_contract_intent = any(term in q for term in ("수의계약", "1인", "견적", "우선구매", "금액", "한도"))
    return has_product_status and has_contract_intent


def _standard_card_id(q: str) -> str | None:
    if _is_vat_threshold_basis_question(q):
        return None

    if _is_innovation_or_certified_product_contract_question(q):
        return None

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

    if _has_agency_law_conflict(q):
        return GatewayDecision(
            route="complex_router",
            confidence="ambiguous",
            reason="agency_law_conflict_requires_legal_context",
            exclusions=exclusions,
            llm_validation_required=True,
        )

    if _has_procurement_design_question(q):
        return GatewayDecision(
            route="complex_router",
            confidence="ambiguous",
            reason="procurement_design_question_requires_context",
            exclusions=exclusions,
            llm_validation_required=True,
        )

    if _is_pure_company_lookup_request(user_message):
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
