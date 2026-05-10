"""Route resolver built on a shared procurement intent frame.

This module is deliberately deterministic.  It does not re-classify the user
question from scratch; it consumes the signals already produced by
normalization, Keyword Router, Intent RAG, and the optional LLM adjudicator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

try:
    from app.router.intent_normalization import normalize_query_intent
except Exception:  # Runtime path when app/ is on sys.path.
    from router.intent_normalization import normalize_query_intent


CONTRACT_METHOD_TERMS = (
    "수의계약", "수의", "1인견적", "2인견적", "견적", "입찰", "경쟁입찰",
    "제한입찰", "지역제한", "공동도급", "MAS", "mas", "다수공급자",
    "종합쇼핑몰", "2단계경쟁", "2단계 경쟁",
)

BROAD_GOODS_ALTERNATIVE_TERMS = (
    "계약방법", "계약방식", "계약경로", "구매방법", "구매경로", "처리방법",
    "방법안내", "경로안내", "대안", "가능한방법", "어떻게계약", "어떻게구매",
    "지역업체", "부산업체", "지역상품", "부산상품", "우선구매",
    "혁신제품", "혁신시제품", "기술개발제품", "우수조달", "성능인증",
    "nep", "net", "gs인증",
)

MAS_TERMS = ("종합쇼핑몰", "mas", "다수공급자", "2단계경쟁", "2단계")
SME_TERMS = ("중기간", "중소기업자간", "경쟁제품", "직접생산")
TECH_PRODUCT_TERMS = (
    "혁신제품", "혁신시제품", "기술개발제품", "우수조달", "성능인증",
    "신제품", "신기술", "nep", "net", "gs인증",
)

FAST_COMPANY_LABELS = {
    "company_search",
    "policy_candidate_search",
    "shopping_mall_search",
    "certified_product_search",
    "innovation_product_search",
    "excellent_procurement_search",
    "company_detail",
    "license_search",
    "mas_search",
}

OBJECT_TO_LABEL = {
    "goods": "item_purchase",
    "service": "service_contract",
    "construction": "construction_contract",
}


@dataclass(frozen=True)
class IntentFrame:
    """Unified NLU output for downstream routing and retrieval planning."""

    original_text: str
    labels: tuple[str, ...] = ()
    sub_intents: tuple[str, ...] = ()
    amount: int | None = None
    item_name: str = ""
    item_search_term: str = ""
    contract_object: str = ""
    contract_object_candidates: tuple[str, ...] = ()
    buyer_type: str = ""
    company_search_required: bool = False
    company_search_blocked: bool = False
    company_search_only: bool = False
    local_purchase_support_required: bool = False
    contract_review_required: bool = False
    procedure_required: bool = False
    procedure_blocked: bool = False
    legal_basis_required: bool = False
    interpretation_required: bool = False
    has_contract_method: bool = False
    issue_tags: tuple[str, ...] = ()
    conflicts: tuple[str, ...] = ()
    missing_slots: tuple[str, ...] = ()
    confidence: float = 0.5
    confidence_level: str = "medium"
    sources: dict[str, Any] = field(default_factory=dict)

    def to_meta(self) -> dict[str, Any]:
        meta = asdict(self)
        meta["labels"] = list(self.labels)
        meta["sub_intents"] = list(self.sub_intents)
        meta["contract_object_candidates"] = list(self.contract_object_candidates)
        meta["issue_tags"] = list(self.issue_tags)
        meta["conflicts"] = list(self.conflicts)
        meta["missing_slots"] = list(self.missing_slots)
        return meta


@dataclass(frozen=True)
class RoutePlan:
    """Execution plan derived from an IntentFrame."""

    query_tier: int = 1
    execution_mode: str = "general_answer"
    answer_sections: tuple[str, ...] = ()
    retrieval_needs: tuple[str, ...] = ()
    evidence_topics: tuple[str, ...] = ()
    negative_constraints: tuple[str, ...] = ()
    candidate_policy: dict[str, Any] = field(default_factory=dict)
    quality_controls: tuple[str, ...] = ()
    company_search_mode: str = "none"  # none | candidates_only | route_relevant_candidates
    legal_review_required: bool = False
    use_fast_track: bool = False
    clarification_required: bool = False
    reasons: tuple[str, ...] = ()

    def to_meta(self) -> dict[str, Any]:
        meta = asdict(self)
        meta["answer_sections"] = list(self.answer_sections)
        meta["retrieval_needs"] = list(self.retrieval_needs)
        meta["evidence_topics"] = list(self.evidence_topics)
        meta["negative_constraints"] = list(self.negative_constraints)
        meta["quality_controls"] = list(self.quality_controls)
        meta["reasons"] = list(self.reasons)
        return meta


def _append_unique(items: list[str], *values: str) -> None:
    for value in values:
        if value and value not in items:
            items.append(value)


def _as_list(value: Any) -> list[str]:
    return [str(v) for v in (value or []) if str(v)]


def _get_slots(router_result) -> Any:
    return getattr(router_result, "slots", None) if router_result is not None else None


def _router_intents(router_result) -> list[str]:
    if router_result is None:
        return []
    return _as_list([getattr(router_result, "primary_intent", "")]) + _as_list(
        getattr(router_result, "secondary_intents", []) or []
    )


def _has_contract_method(text: str) -> bool:
    return any(term in (text or "") for term in CONTRACT_METHOD_TERMS)


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _has_explicit_local_support_signal(text: str) -> bool:
    q = _compact(text)
    return any(term in q for term in (
        "부산", "지역업체", "부산업체", "지역상품", "부산상품",
        "지역제한", "지역가점", "지역의무", "지역업체참여", "지역업체참여도",
        "공동도급", "공동수급", "지역경제",
    ))


def _resolve_confidence(keyword_result=None, intent_rag_decision=None, router_result=None) -> tuple[float, str]:
    score = 0.45
    if bool(getattr(keyword_result, "is_unambiguous", False)):
        score += 0.15
    try:
        rag_conf = float(getattr(intent_rag_decision, "confidence", 0.0) or 0.0)
    except Exception:
        rag_conf = 0.0
    if rag_conf:
        score += min(0.25, max(0.0, (rag_conf - 0.5) * 0.45))
    try:
        router_conf = float(getattr(router_result, "confidence", 0.0) or 0.0)
    except Exception:
        router_conf = 0.0
    if router_conf:
        score += min(0.2, max(0.0, (router_conf - 0.5) * 0.4))

    score = round(max(0.0, min(1.0, score)), 2)
    if score >= 0.75:
        return score, "high"
    if score >= 0.55:
        return score, "medium"
    return score, "low"


def build_intent_frame(
    user_message: str,
    *,
    keyword_result=None,
    intent_rag_decision=None,
    router_result=None,
    intent_labels: list[str] | tuple[str, ...] | None = None,
    gateway_decision=None,
) -> IntentFrame:
    """Merge deterministic and optional LLM signals into a single intent frame."""
    norm = normalize_query_intent(user_message or "")
    labels: list[str] = []
    for label in intent_labels or []:
        if label and label != "unclear":
            _append_unique(labels, label)

    for label in _as_list(getattr(keyword_result, "matched_categories", []) or []):
        if label != "unclear":
            _append_unique(labels, label)

    rag_confidence = 0.0
    sub_intents: list[str] = []
    if intent_rag_decision is not None:
        try:
            rag_confidence = float(getattr(intent_rag_decision, "confidence", 0.0) or 0.0)
        except Exception:
            rag_confidence = 0.0
        if rag_confidence >= 0.55:
            for label in _as_list(getattr(intent_rag_decision, "intent_labels", []) or []):
                if label == "company_search" and not bool(getattr(intent_rag_decision, "company_search_required", False)):
                    continue
                _append_unique(labels, label)
        for sub_intent in _as_list(getattr(intent_rag_decision, "sub_intents", []) or []):
            _append_unique(sub_intents, sub_intent)

    for intent in _router_intents(router_result):
        mapping = {
            "candidate_search": "company_search",
            "legal_explanation": "legal_explanation",
            "contract_review": "contract_review",
            "local_purchase_support": "local_purchase_support",
            "item_eligibility": "item_eligibility",
            "procurement_route_review": "procurement_route_review",
            "mixed": "mixed_contract",
        }
        _append_unique(labels, mapping.get(intent, intent))

    if norm.contract_object:
        _append_unique(labels, OBJECT_TO_LABEL.get(norm.contract_object, ""))
    if norm.contract_review_requested or norm.amount is not None:
        _append_unique(labels, "contract_review")
    if norm.procedure_requested and not norm.procedure_blocked:
        _append_unique(labels, "procedure")
    if norm.local_support_requested:
        _append_unique(labels, "local_purchase_support")
    if norm.legal_basis_requested:
        _append_unique(labels, "legal_explanation")

    slots = _get_slots(router_result)
    item_name = norm.item_name or str(getattr(slots, "item_name", "") or "")
    amount = norm.amount if norm.amount is not None else getattr(slots, "amount", None)
    contract_object = norm.contract_object or str(getattr(slots, "contract_object", "") or "")
    buyer_type = norm.buyer_type or str(getattr(slots, "buyer_type", "") or "")

    company_required = (
        norm.company_lookup_requested
        or bool(getattr(intent_rag_decision, "company_search_required", False))
        or bool(getattr(router_result, "candidate_lookup_required", False))
        or bool(getattr(router_result, "company_lookup_required", False))
        or "company_search" in labels
    )
    company_blocked = norm.company_lookup_blocked or bool(getattr(intent_rag_decision, "company_search_blocked", False))
    if company_blocked:
        labels = [label for label in labels if label != "company_search"]
        company_required = False
    elif company_required:
        _append_unique(labels, "company_search")

    explicit_local_signal = norm.local_support_requested or _has_explicit_local_support_signal(user_message)
    if not explicit_local_signal and "local_purchase_support" in labels:
        labels = [label for label in labels if label != "local_purchase_support"]
    local_required = bool(
        explicit_local_signal
        and (
            norm.local_support_requested
            or bool(getattr(intent_rag_decision, "local_purchase_support_required", False))
            or bool(getattr(router_result, "local_purchase_support_required", False))
            or "local_purchase_support" in labels
        )
    )
    contract_review_required = norm.contract_review_requested or bool(getattr(intent_rag_decision, "contract_review_required", False)) or bool(getattr(router_result, "legal_review_required", False)) or "contract_review" in labels
    procedure_required = norm.procedure_requested and not norm.procedure_blocked or bool(getattr(intent_rag_decision, "procedure_required", False)) or "procedure" in labels
    legal_basis_required = norm.legal_basis_requested or bool(getattr(intent_rag_decision, "legal_basis_required", False)) or "legal_explanation" in labels or contract_review_required

    conflicts: list[str] = []
    missing: list[str] = []
    if company_blocked and "company_search" in labels:
        conflicts.append("company_search_blocked_but_label_present")
    if "mixed_contract_object" in norm.issue_tags:
        conflicts.append("mixed_contract_object")
    if "agency_type_conflict" in norm.issue_tags:
        conflicts.append("agency_type_conflict")
    if company_required and not item_name:
        missing.append("item_name")
    if (amount is not None or _has_contract_method(user_message)) and not (contract_object or item_name):
        missing.append("contract_object_or_item")

    confidence, confidence_level = _resolve_confidence(keyword_result, intent_rag_decision, router_result)
    if conflicts or missing:
        confidence = min(confidence, 0.64)
        confidence_level = "medium" if confidence >= 0.55 else "low"

    if not labels:
        labels = ["common_procurement"]

    return IntentFrame(
        original_text=user_message,
        labels=tuple(labels),
        sub_intents=tuple(sub_intents),
        amount=amount,
        item_name=item_name,
        item_search_term=norm.item_search_term or item_name,
        contract_object=contract_object,
        contract_object_candidates=norm.contract_object_candidates,
        buyer_type=buyer_type,
        company_search_required=company_required,
        company_search_blocked=company_blocked,
        company_search_only=norm.company_lookup_only,
        local_purchase_support_required=local_required,
        contract_review_required=contract_review_required,
        procedure_required=procedure_required,
        procedure_blocked=norm.procedure_blocked,
        legal_basis_required=legal_basis_required,
        interpretation_required=norm.interpretation_requested,
        has_contract_method=_has_contract_method(user_message),
        issue_tags=norm.issue_tags,
        conflicts=tuple(dict.fromkeys(conflicts)),
        missing_slots=tuple(dict.fromkeys(missing)),
        confidence=confidence,
        confidence_level=confidence_level,
        sources={
            "gateway_route": getattr(gateway_decision, "route", None),
            "keyword_categories": _as_list(getattr(keyword_result, "matched_categories", []) or []),
            "intent_rag_confidence": rag_confidence,
            "llm_adjudicated": router_result is not None,
        },
    )


def resolve_route_plan(frame: IntentFrame) -> RoutePlan:
    """Translate a finalized IntentFrame into execution needs."""
    labels = set(frame.labels)
    reasons: list[str] = []
    sections: list[str] = []
    retrieval: list[str] = []
    evidence_topics: list[str] = []
    negative_constraints: list[str] = []
    quality_controls: list[str] = [
        "use_intent_frame_slots_as_source_of_truth",
        "do_not_reclassify_question_in_later_steps",
    ]
    q = _compact(frame.original_text)

    company_mode = "none"
    if frame.company_search_required and not frame.company_search_blocked:
        company_mode = "candidates_only" if frame.company_search_only else "route_relevant_candidates"
        _append_unique(sections, "company_candidates")
        _append_unique(retrieval, "company_candidates")
        reasons.append(f"company_search:{company_mode}")
    if frame.company_search_blocked:
        _append_unique(negative_constraints, "omit_company_candidates")
        _append_unique(quality_controls, "respect_user_request_to_exclude_company_names")

    if frame.contract_review_required or frame.amount is not None or frame.has_contract_method:
        _append_unique(sections, "contract_summary", "procurement_routes")
        _append_unique(retrieval, "purchase_route_cards", "legal_basis")
        _append_unique(evidence_topics, "amount_based_contract_route", "direct_contract_thresholds")
        reasons.append("contract_review_or_amount")

    if frame.procedure_required:
        _append_unique(sections, "procedure")
        _append_unique(retrieval, "practice_manual")
        _append_unique(evidence_topics, "procurement_lifecycle_procedure")
        reasons.append("procedure_requested")

    if frame.local_purchase_support_required:
        _append_unique(sections, "local_support")
        _append_unique(retrieval, "regional_support_catalog")
        _append_unique(evidence_topics, "regional_support_methods")
        reasons.append("local_purchase_support")

    if frame.legal_basis_required:
        _append_unique(sections, "legal_basis")
        _append_unique(retrieval, "legal_basis")

    if "item_eligibility" in labels or "item_purchase" in labels:
        _append_unique(retrieval, "item_eligibility")
        _append_unique(evidence_topics, "item_eligibility")
        if frame.amount is not None or frame.contract_review_required or frame.has_contract_method:
            broad_goods_alternatives = _has_any(q, BROAD_GOODS_ALTERNATIVE_TERMS)
            explicit_mas = _has_any(q, MAS_TERMS)
            explicit_sme = _has_any(q, SME_TERMS)
            explicit_tech_product = _has_any(q, TECH_PRODUCT_TERMS)

            if explicit_mas or broad_goods_alternatives:
                _append_unique(evidence_topics, "mas_shopping_mall", "mas_second_stage_competition")
            if explicit_sme or broad_goods_alternatives:
                _append_unique(evidence_topics, "sme_competition_product")
            if explicit_tech_product or broad_goods_alternatives:
                _append_unique(evidence_topics, "innovation_or_technology_development_product")
            _append_unique(quality_controls, "cover_goods_purchase_alternative_routes")

    if (
        (frame.contract_object in {"service", "construction"} or labels & {"service_contract", "construction_contract"})
        and (frame.local_purchase_support_required or frame.company_search_required or frame.contract_review_required)
    ):
        _append_unique(evidence_topics, "regional_restriction_or_local_points")
        _append_unique(quality_controls, "cover_non_goods_regional_support_routes")

    if "mas_shopping_mall" in labels or "종합쇼핑몰" in q or "mas" in q:
        _append_unique(evidence_topics, "mas_shopping_mall", "mas_second_stage_competition")
    if any(term in q for term in ("중기간", "중소기업자간", "경쟁제품")):
        _append_unique(evidence_topics, "sme_competition_product")
    if any(term in q for term in ("혁신제품", "혁신시제품", "기술개발제품", "우수조달", "성능인증", "nep", "net", "gs")):
        _append_unique(evidence_topics, "innovation_or_technology_development_product")
    if any(term in q for term in ("여성기업", "장애인기업", "사회적기업", "중소기업제품구매실적", "구매실적")):
        _append_unique(evidence_topics, "policy_company_purchase_performance")
    if any(term in q for term in ("지역제한", "지역의무", "공동도급", "가점", "지역업체참여도")):
        _append_unique(evidence_topics, "regional_restriction_or_local_points")
    if "mixed_contract_object" in frame.issue_tags:
        _append_unique(evidence_topics, "mixed_contract_object")
        _append_unique(quality_controls, "avoid_single_contract_object_assumption")
    if "agency_type_conflict" in frame.issue_tags:
        _append_unique(evidence_topics, "agency_law_scope_conflict")
        _append_unique(quality_controls, "separate_national_local_public_enterprise_rules")
    if "split_procurement_review" in frame.issue_tags:
        _append_unique(evidence_topics, "split_procurement_review")
    if "construction_period_extension" in frame.issue_tags:
        _append_unique(evidence_topics, "construction_period_extension")
    if "indirect_cost_review" in frame.issue_tags:
        _append_unique(evidence_topics, "indirect_cost_review")

    clarification_required = bool(frame.missing_slots and frame.confidence_level == "low")
    if clarification_required:
        _append_unique(sections, "clarification")
        reasons.append("low_confidence_missing_slots")

    query_tier = 1
    use_fast_track = False
    execution_mode = "general_answer"
    if (
        company_mode == "candidates_only"
        and not frame.amount
        and not frame.has_contract_method
        and not frame.contract_review_required
        and not frame.legal_basis_required
    ):
        query_tier = 0
        use_fast_track = True
        execution_mode = "company_fast_track"
        reasons.append("pure_company_candidate_lookup")
    elif frame.buyer_type in {"public_enterprise"} or any(term in frame.original_text for term in ("부산교통공사", "출자출연", "공기업", "시설공단", "환경공단")):
        query_tier = 3
        execution_mode = "agency_specific"
        reasons.append("agency_specific_question")
    elif frame.amount is not None and (frame.item_name or frame.contract_object or frame.local_purchase_support_required or frame.has_contract_method):
        query_tier = 2
        execution_mode = "evidence_prefetch"
        reasons.append("amount_based_procurement_review")
    elif frame.has_contract_method or frame.conflicts:
        query_tier = 2
        execution_mode = "evidence_prefetch"
        reasons.append("method_or_conflict_requires_legal_context")

    if execution_mode == "general_answer":
        if clarification_required:
            execution_mode = "clarification"
        elif "legal_basis" in retrieval or "regional_support_catalog" in retrieval:
            execution_mode = "evidence_prefetch"
        elif "practice_manual" in retrieval:
            execution_mode = "practice_guided"
        elif company_mode == "route_relevant_candidates":
            execution_mode = "candidate_enriched_answer"

    if not sections:
        _append_unique(sections, "general_answer")
    if not retrieval:
        _append_unique(retrieval, "none")

    candidate_policy = {
        "include_company_candidates": company_mode != "none",
        "mode": company_mode,
        "item_name": frame.item_name,
        "search_term": frame.item_search_term or frame.item_name,
        "include_route_relevant_only": company_mode == "route_relevant_candidates",
        "respect_negative_request": frame.company_search_blocked,
    }
    if company_mode == "route_relevant_candidates":
        candidate_policy["candidate_table_purpose"] = "show suppliers only where they support a viable procurement route"
    elif company_mode == "candidates_only":
        candidate_policy["candidate_table_purpose"] = "supplier lookup only, no legal conclusion"

    return RoutePlan(
        query_tier=query_tier,
        execution_mode=execution_mode,
        answer_sections=tuple(sections),
        retrieval_needs=tuple(retrieval),
        evidence_topics=tuple(dict.fromkeys(evidence_topics)),
        negative_constraints=tuple(dict.fromkeys(negative_constraints)),
        candidate_policy=candidate_policy,
        quality_controls=tuple(dict.fromkeys(quality_controls)),
        company_search_mode=company_mode,
        legal_review_required="legal_basis" in retrieval,
        use_fast_track=use_fast_track,
        clarification_required=clarification_required,
        reasons=tuple(dict.fromkeys(reasons)),
    )


def format_route_plan_for_llm(frame: IntentFrame, plan: RoutePlan) -> str:
    """Compact prompt context. This is a plan, not a second classifier."""
    return "\n".join([
        "[확정 실행계획]",
        f"- 실행 모드: {plan.execution_mode}",
        f"- 의도 라벨: {', '.join(frame.labels) or '없음'}",
        f"- 슬롯: 품목={frame.item_name or '미확인'}, 금액={frame.amount or '미확인'}, 계약대상={frame.contract_object or '미확인'}",
        f"- 업체 후보: {plan.company_search_mode}",
        f"- 답변 섹션: {', '.join(plan.answer_sections)}",
        f"- 조회 필요: {', '.join(plan.retrieval_needs)}",
        f"- 근거 쟁점: {', '.join(plan.evidence_topics) or '없음'}",
        f"- 제외/주의 조건: {', '.join(plan.negative_constraints) or '없음'}",
        f"- 품질 통제: {', '.join(plan.quality_controls) or '없음'}",
        f"- 주의 신호: {', '.join(frame.conflicts or frame.issue_tags) or '없음'}",
        "- 이 실행계획은 질문을 재분류한 결과가 아니라, 앞단 의도판별 신호를 합친 결과입니다.",
    ])
