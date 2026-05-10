"""
Conditional LLM route adjudication.

The adjudicator is not a first-line router. It decides whether the three
cheap signals (normalization, keyword route, Intent RAG) are too ambiguous or
conflicting and, only then, prepares a compact card for an LLM router.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from app.router.intent_normalization import normalize_query_intent
except Exception:  # Runtime path when app/ is on sys.path.
    from router.intent_normalization import normalize_query_intent


RAG_HIGH_CONFIDENCE = 0.78
RAG_VERY_HIGH_CONFIDENCE = 0.86
RAG_LOW_CONFIDENCE = 0.58
GATEWAY_VALIDATION_REASONS = {
    "standard_card_candidate_but_case_specific",
    "agency_law_conflict_requires_legal_context",
    "procurement_design_question_requires_context",
}


@dataclass(frozen=True)
class LlmAdjudicationNeed:
    required: bool
    reasons: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    missing_slots: tuple[str, ...] = ()
    complex_signal_count: int = 0
    rag_confidence: float | None = None
    keyword_unambiguous: bool = False
    bypass_reason: str = ""

    def to_meta(self) -> dict[str, Any]:
        return asdict(self)


def _labels(intent_labels: list[str] | tuple[str, ...] | None) -> set[str]:
    return {str(label) for label in (intent_labels or []) if str(label)}


def _keyword_matched(keyword_result) -> list[str]:
    return list(getattr(keyword_result, "matched_categories", []) or [])


def _keyword_ambiguous(keyword_result) -> list[str]:
    return list(getattr(keyword_result, "ambiguous_keywords", []) or [])


def _rag_confidence(intent_rag_decision) -> float | None:
    if intent_rag_decision is None:
        return None
    try:
        return float(getattr(intent_rag_decision, "confidence", 0.0) or 0.0)
    except Exception:
        return None


def _has_method_or_route(text: str) -> bool:
    compact = (text or "").replace(" ", "").lower()
    return any(term in compact for term in (
        "수의계약", "수의", "1인견적", "2인견적", "견적", "입찰",
        "지역제한", "공동도급", "종합쇼핑몰", "mas", "다수공급자", "제3자단가",
    ))


def _has_procedure_or_strategy(text: str) -> bool:
    compact = (text or "").replace(" ", "").lower()
    return any(term in compact for term in (
        "절차", "프로세스", "방법", "방안", "경로", "검토", "가능", "활용",
        "우대", "가점", "기준", "근거", "어떻게", "해야",
    ))


def evaluate_llm_adjudication_need(
    user_message: str,
    *,
    gateway_decision=None,
    keyword_result=None,
    intent_rag_decision=None,
    intent_labels: list[str] | tuple[str, ...] | None = None,
) -> LlmAdjudicationNeed:
    """Return a deterministic decision on whether LLM route adjudication is needed."""
    text = user_message or ""
    norm = normalize_query_intent(text)
    labels = _labels(intent_labels)
    matched = _keyword_matched(keyword_result)
    ambiguous_keywords = _keyword_ambiguous(keyword_result)
    keyword_unambiguous = bool(getattr(keyword_result, "is_unambiguous", False))
    rag_conf = _rag_confidence(intent_rag_decision)

    reasons: list[str] = []
    conflicts: list[str] = []
    missing: list[str] = []

    gateway_route = getattr(gateway_decision, "route", None)
    if gateway_route in {"direct_article", "standard_card", "company_search"}:
        return LlmAdjudicationNeed(
            required=False,
            rag_confidence=rag_conf,
            keyword_unambiguous=keyword_unambiguous,
            bypass_reason=f"gateway_fast_exit:{gateway_route}",
        )

    gateway_reason = str(getattr(gateway_decision, "reason", "") or "")
    if (
        bool(getattr(gateway_decision, "llm_validation_required", False))
        and gateway_reason in GATEWAY_VALIDATION_REASONS
    ):
        reasons.append("gateway_validation_required")

    if not matched or matched == ["unclear"] or "unclear" in matched:
        reasons.append("keyword_unclear")
    if ambiguous_keywords:
        reasons.append("keyword_ambiguous:" + ",".join(ambiguous_keywords[:4]))
    if len([m for m in matched if m != "unclear"]) >= 3 and not keyword_unambiguous:
        reasons.append("keyword_multi_route")

    if rag_conf is None:
        reasons.append("intent_rag_unavailable")
    elif rag_conf < RAG_LOW_CONFIDENCE:
        reasons.append(f"intent_rag_low_confidence:{rag_conf:.2f}")
    elif rag_conf < RAG_HIGH_CONFIDENCE and not keyword_unambiguous:
        reasons.append(f"intent_rag_medium_confidence:{rag_conf:.2f}")

    company_label = "company_search" in labels
    rag_blocks_company = bool(getattr(intent_rag_decision, "company_search_blocked", False))
    rag_requires_company = bool(getattr(intent_rag_decision, "company_search_required", False))
    if rag_blocks_company and company_label:
        conflicts.append("intent_rag_blocks_company_search_but_label_present")
    if rag_requires_company and not company_label:
        conflicts.append("intent_rag_requires_company_search_but_label_missing")
    if norm.company_lookup_blocked and company_label:
        conflicts.append("normalization_blocks_company_search_but_label_present")
    if norm.company_lookup_requested and not norm.company_lookup_blocked and not company_label:
        conflicts.append("normalization_requires_company_search_but_label_missing")
    if "mixed_contract_object" in norm.issue_tags:
        conflicts.append("mixed_contract_object_requires_final_route_check")
    if "agency_type_conflict" in norm.issue_tags:
        conflicts.append("agency_type_conflict_requires_final_route_check")

    has_amount = norm.amount is not None
    has_item = bool(norm.item_name)
    has_contract_object = bool(norm.contract_object)
    has_mixed_contract_object = "mixed_contract_object" in norm.issue_tags
    has_agency_type_conflict = "agency_type_conflict" in norm.issue_tags
    has_local = bool(norm.local_support_requested)
    has_method_or_route = _has_method_or_route(text)
    has_strategy = _has_procedure_or_strategy(text)

    if company_label and not has_item:
        missing.append("item_name_for_company_search")
    if (has_amount or has_method_or_route or has_local) and not (has_contract_object or has_item):
        missing.append("contract_object_or_item")

    if company_label and (has_amount or has_method_or_route or has_strategy) and not norm.company_lookup_only:
        conflicts.append("company_search_label_may_be_purchase_route_guidance")

    complex_signal_count = sum([
        has_amount,
        has_item,
        has_contract_object,
        has_local,
        has_method_or_route,
        has_strategy,
        norm.company_lookup_requested,
        has_mixed_contract_object,
        has_agency_type_conflict,
        len(text) >= 120,
    ])
    if complex_signal_count >= 4 and (rag_conf is None or rag_conf < RAG_HIGH_CONFIDENCE):
        reasons.append(f"complex_multi_signal:{complex_signal_count}")

    route_labels = labels | {m for m in matched if m and m != "unclear"}
    purchase_route_labels = {
        "item_purchase",
        "contract_review",
        "procurement_route_review",
        "mas_shopping_mall",
        "sole_contract",
        "common_procurement",
    }
    if (
        has_amount
        and has_item
        and has_method_or_route
        and route_labels
        and route_labels.issubset(purchase_route_labels)
        and not has_local
        and not norm.company_lookup_requested
        and not company_label
        and not has_mixed_contract_object
        and not has_agency_type_conflict
        and not conflicts
        and not missing
        and not ambiguous_keywords
    ):
        return LlmAdjudicationNeed(
            required=False,
            rag_confidence=rag_conf,
            keyword_unambiguous=keyword_unambiguous,
            complex_signal_count=complex_signal_count,
            bypass_reason="explicit_purchase_route_signals_sufficient",
        )

    if (
        rag_conf is not None
        and rag_conf >= RAG_VERY_HIGH_CONFIDENCE
        and not conflicts
        and not missing
        and not ambiguous_keywords
        and "unclear" not in matched
        and gateway_reason not in GATEWAY_VALIDATION_REASONS
    ):
        return LlmAdjudicationNeed(
            required=False,
            rag_confidence=rag_conf,
            keyword_unambiguous=keyword_unambiguous,
            complex_signal_count=complex_signal_count,
            bypass_reason="high_confidence_rag_without_conflict",
        )

    required = bool(reasons or conflicts or missing)
    return LlmAdjudicationNeed(
        required=required,
        reasons=tuple(dict.fromkeys(reasons)),
        conflicts=tuple(dict.fromkeys(conflicts)),
        missing_slots=tuple(dict.fromkeys(missing)),
        complex_signal_count=complex_signal_count,
        rag_confidence=rag_conf,
        keyword_unambiguous=keyword_unambiguous,
        bypass_reason="" if required else "deterministic_signals_sufficient",
    )


def build_llm_adjudication_card(
    user_message: str,
    *,
    gateway_decision=None,
    keyword_result=None,
    intent_rag_decision=None,
    intent_labels: list[str] | tuple[str, ...] | None = None,
    need: LlmAdjudicationNeed | None = None,
) -> dict[str, Any]:
    """Build a compact, JSON-serializable card for the LLM route adjudicator."""
    norm = normalize_query_intent(user_message or "")
    rag_meta = {}
    if intent_rag_decision is not None:
        try:
            rag_meta = intent_rag_decision.to_meta()
        except Exception:
            rag_meta = {
                "primary_intent": getattr(intent_rag_decision, "primary_intent", ""),
                "intent_labels": list(getattr(intent_rag_decision, "intent_labels", []) or []),
                "confidence": getattr(intent_rag_decision, "confidence", 0.0),
            }
    return {
        "user_message": user_message,
        "decision_scope": "final_routing_only_no_answer_generation",
        "adjudication_need": need.to_meta() if need else {},
        "gateway": {
            "route": getattr(gateway_decision, "route", None),
            "confidence": getattr(gateway_decision, "confidence", None),
            "reason": getattr(gateway_decision, "reason", ""),
            "llm_validation_required": bool(getattr(gateway_decision, "llm_validation_required", False)),
            "exclusions": list(getattr(gateway_decision, "exclusions", []) or []),
        },
        "normalization": {
            "amount": norm.amount,
            "item_name": norm.item_name,
            "contract_object": norm.contract_object,
            "contract_object_candidates": list(norm.contract_object_candidates),
            "buyer_type": norm.buyer_type,
            "company_lookup_requested": norm.company_lookup_requested,
            "company_lookup_blocked": norm.company_lookup_blocked,
            "company_lookup_only": norm.company_lookup_only,
            "local_support_requested": norm.local_support_requested,
            "contract_review_requested": norm.contract_review_requested,
            "search_text": norm.search_text,
            "issue_tags": list(norm.issue_tags),
        },
        "keyword_router": {
            "matched_categories": _keyword_matched(keyword_result),
            "ambiguous_keywords": _keyword_ambiguous(keyword_result),
            "is_unambiguous": bool(getattr(keyword_result, "is_unambiguous", False)),
            "forced_guardrails": list(getattr(keyword_result, "forced_guardrails", []) or []),
        },
        "intent_rag": {
            "primary_intent": rag_meta.get("primary_intent", ""),
            "intent_labels": rag_meta.get("intent_labels", []),
            "sub_intents": rag_meta.get("sub_intents", []),
            "answer_mode": rag_meta.get("answer_mode", ""),
            "confidence": rag_meta.get("confidence", 0.0),
            "confidence_level": rag_meta.get("confidence_level", ""),
            "company_search_required": rag_meta.get("company_search_required", False),
            "company_search_blocked": rag_meta.get("company_search_blocked", False),
            "local_purchase_support_required": rag_meta.get("local_purchase_support_required", False),
            "contract_review_required": rag_meta.get("contract_review_required", False),
            "procedure_required": rag_meta.get("procedure_required", False),
            "legal_basis_required": rag_meta.get("legal_basis_required", False),
            "matched_examples": (rag_meta.get("matched_examples", []) or [])[:3],
            "reasons": rag_meta.get("reasons", []),
        },
        "current_labels_before_adjudication": list(intent_labels or []),
        "task": {
            "return": "RouterResult JSON only",
            "must_decide": [
                "primary_intent",
                "secondary_intents",
                "slots",
                "routing_decision",
                "candidate_lookup_required",
                "legal_review_required",
                "local_purchase_support_required",
                "answer_focus",
            ],
            "do_not": [
                "answer the procurement question",
                "make a legal conclusion",
                "invent legal thresholds",
                "invent company eligibility",
            ],
        },
    }
