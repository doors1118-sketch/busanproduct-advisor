"""
Routing confidence/ambiguity assessment.

This module does not replace the existing keyword/gateway/Gemini router stack.
It records how much those signals agree and suggests conservative routing when
the intent is unclear.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any


@dataclass
class RoutingConfidence:
    score: float
    level: str
    ambiguous: bool
    reasons: list[str] = field(default_factory=list)
    required_slots_missing: list[str] = field(default_factory=list)
    action: str = "proceed"
    tier_override: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _has_amount(text: str) -> bool:
    return bool(re.search(r"\d+(?:\.\d+)?\s*(?:억|천만|백만|만원|원)", text or ""))


def _has_contract_method(text: str) -> bool:
    return any(term in (text or "") for term in (
        "수의계약", "수의", "견적", "입찰", "지역제한", "공동도급", "MAS", "다수공급자",
    ))


def _has_legal_terms(text: str) -> bool:
    return any(term in (text or "") for term in (
        "법", "시행령", "시행규칙", "행정규칙", "예규", "고시", "기준", "조문", "제",
    ))


def _has_specific_item_alias(text: str) -> bool:
    compact = (text or "").replace(" ", "").lower()
    return any(term in compact for term in (
        "led", "led등", "led조명", "엘이디", "엘이디등", "엘이디조명",
        "cctv", "씨씨티비", "영상감시장치",
        "컴퓨터", "프린터", "복사기", "에어컨", "냉난방", "가구", "의자", "책상", "차량", "서버", "조명",
        "청소", "경비", "소프트웨어",
    ))


def _router_confidence(router_result) -> float | None:
    if router_result is None:
        return None
    try:
        value = float(getattr(router_result, "confidence", 0.0) or 0.0)
    except Exception:
        return None
    return max(0.0, min(1.0, value))


def assess_routing_confidence(
    user_message: str,
    *,
    gateway_decision=None,
    keyword_result=None,
    router_result=None,
    intent_labels: list[str] | None = None,
    query_tier: int = 1,
) -> RoutingConfidence:
    """Score routing certainty from deterministic and LLM-assisted signals."""
    intent_labels = intent_labels or []
    score = 0.35
    reasons: list[str] = []
    missing: list[str] = []

    gateway_conf = getattr(gateway_decision, "confidence", None)
    gateway_route = getattr(gateway_decision, "route", None)
    if gateway_conf == "certain":
        score += 0.2
        if gateway_route in {"company_search", "direct_article", "standard_card"}:
            score += 0.15
    else:
        reasons.append(f"gateway:{getattr(gateway_decision, 'reason', 'ambiguous')}")
        score -= 0.05

    if keyword_result is not None:
        if bool(getattr(keyword_result, "is_unambiguous", False)):
            score += 0.15
        else:
            amb = list(getattr(keyword_result, "ambiguous_keywords", []) or [])
            reasons.append("keyword_ambiguous" + (f":{','.join(amb[:4])}" if amb else ""))
            score -= 0.05

    rc = _router_confidence(router_result)
    if rc is None:
        if gateway_route == "complex_router":
            reasons.append("llm_router_not_available_for_complex_query")
            score -= 0.1
    else:
        score += (rc - 0.5) * 0.35
        if rc < 0.65:
            reasons.append(f"llm_router_low_confidence:{rc:.2f}")

    has_amount = _has_amount(user_message)
    has_contract_method = _has_contract_method(user_message)
    has_legal_terms = _has_legal_terms(user_message)
    company_intent = any(label in intent_labels for label in (
        "company_search", "policy_candidate_search", "shopping_mall_search",
        "certified_product_search", "innovation_product_search",
    ))

    if query_tier == 0 and (has_amount or has_contract_method or has_legal_terms):
        reasons.append("tier0_conflicts_with_legal_or_amount_terms")
        score -= 0.25

    slots = getattr(router_result, "slots", None)
    if (has_amount or has_contract_method) and not getattr(slots, "contract_object", None):
        missing.append("contract_object")
    if has_contract_method and not getattr(slots, "contract_method", None):
        missing.append("contract_method")
    if company_intent and not getattr(slots, "item_name", None) and not _has_specific_item_alias(user_message):
        missing.append("item_name")
    if missing:
        score -= min(0.2, 0.07 * len(missing))
        reasons.append("required_slots_missing")

    score = round(max(0.0, min(1.0, score)), 2)
    if score >= 0.75:
        level = "high"
    elif score >= 0.55:
        level = "medium"
    else:
        level = "low"

    ambiguous = level == "low" or bool(reasons)
    action = "proceed"
    tier_override = None
    if query_tier == 0 and ambiguous and (has_amount or has_contract_method or has_legal_terms):
        action = "avoid_fast_track"
        tier_override = 2 if has_contract_method or has_amount else 1
    elif level == "low":
        action = "proceed_with_clarification_bias"

    return RoutingConfidence(
        score=score,
        level=level,
        ambiguous=ambiguous,
        reasons=reasons,
        required_slots_missing=missing,
        action=action,
        tier_override=tier_override,
    )
