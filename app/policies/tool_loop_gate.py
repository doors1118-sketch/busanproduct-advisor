"""Policy gate for the LLM tool loop.

The goal is not to remove tool use.  This module makes the handoff explicit:
system collectors gather internal DB/catalog/company evidence first, and the
LLM tool loop is reserved for cases where those prepared facts are insufficient
or ambiguous.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
import re
from typing import Any


TOOL_LOOP_GATE_MODE = os.getenv("TOOL_LOOP_GATE_MODE", "shadow").lower()


@dataclass(frozen=True)
class ToolLoopGateDecision:
    recommendation: str
    evidence_sufficiency_score: float
    should_allow_loop: bool
    can_use_writer_only: bool
    mode: str = TOOL_LOOP_GATE_MODE
    reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    expected_supports: list[str] = field(default_factory=list)
    covered_supports: list[str] = field(default_factory=list)
    missing_supports: list[str] = field(default_factory=list)
    evidence_coverage_status: str = "not_checked"
    evidence_coverage_score: float = 0.0
    required_evidence_topics: list[str] = field(default_factory=list)
    covered_evidence_topics: list[str] = field(default_factory=list)
    partial_evidence_topics: list[str] = field(default_factory=list)
    missing_evidence_topics: list[str] = field(default_factory=list)
    evidence_hit_count: int = 0
    evidence_missing_count: int = 0
    internal_db_hit_count: int = 0
    practice_manual_card_count: int = 0
    pps_qa_card_count: int = 0

    def to_meta(self) -> dict[str, Any]:
        meta = asdict(self)
        return {f"tool_loop_gate_{key}": value for key, value in meta.items()}


def _compact(text: str) -> str:
    return (text or "").lower().replace(" ", "").replace("ㆍ", "").replace("·", "")


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    compact = _compact(text)
    return any(_compact(term) in compact for term in terms)


def _expected_supports(user_message: str) -> list[str]:
    expected: list[str] = []

    checks = [
        (("수의계약", "수의", "계약가능", "계약 가능"), "direct_contract"),
        (("1인견적", "1인 견적", "단일견적"), "one_person_quote"),
        (("금액", "한도", "얼마", "억원", "천만원", "만원"), "amount_threshold"),
        (("지역제한", "지역 제한", "제한경쟁"), "regional_restriction"),
        (("지역업체가점", "지역 업체 가점", "지역업체 가점", "신인도", "배점"), "local_company_point"),
        (("공동도급", "공동계약", "의무공동도급"), "joint_contract"),
        (("mas", "다수공급자", "종합쇼핑몰", "나라장터"), "mas"),
        (("우선구매", "의무구매", "중소기업제품", "직접생산"), "priority_purchase"),
        (("별표", "별지", "서식", "평가표", "배점표"), "annex_or_form"),
    ]
    for terms, label in checks:
        if _has_any(user_message, terms) and label not in expected:
            expected.append(label)

    if _has_any(user_message, ("혁신제품", "혁신시제품", "우수조달", "기술개발제품")):
        for label in ("direct_contract", "priority_purchase"):
            if label not in expected:
                expected.append(label)

    if _has_any(user_message, ("분리발주", "분리 발주", "분리도급", "분리 도급")):
        for label in ("direct_contract", "annex_or_form"):
            if label not in expected:
                expected.append(label)

    return expected


def _evidence_counts(evidence_cards: list[dict[str, Any]] | None) -> tuple[int, int, int, set[str]]:
    hits = 0
    missing = 0
    internal_hits = 0
    supports: set[str] = set()

    for card in evidence_cards or []:
        if card.get("status") == "hit":
            hits += 1
            supports.update(str(item) for item in (card.get("supports") or []))
            supports.update(str(item) for item in (card.get("applicability") or []))
            if card.get("source") == "internal_db":
                internal_hits += 1
        else:
            missing += 1

    return hits, missing, internal_hits, supports


def _assess_coverage_if_possible(
    *,
    route_plan: Any = None,
    evidence_cards: list[dict[str, Any]] | None = None,
    practice_manual_cards: list[Any] | None = None,
    pps_qa_cards: list[Any] | None = None,
    evidence_coverage: Any = None,
):
    if evidence_coverage is not None:
        return evidence_coverage
    if route_plan is None:
        return None
    try:
        try:
            from .evidence_coverage_policy import assess_evidence_coverage
        except ImportError:
            from policies.evidence_coverage_policy import assess_evidence_coverage
        return assess_evidence_coverage(
            route_plan=route_plan,
            evidence_cards=evidence_cards,
            practice_manual_cards=practice_manual_cards,
            pps_qa_cards=pps_qa_cards,
        )
    except Exception:
        return None


def _coverage_attr(coverage: Any, name: str, default=None):
    if coverage is None:
        return default
    if isinstance(coverage, dict):
        return coverage.get(name, default)
    return getattr(coverage, name, default)


def _semantic_ambiguity_reasons(user_message: str) -> list[str]:
    reasons: list[str] = []
    compact = _compact(user_message)

    agency_terms = [
        term for term in ("국가기관", "국가계약", "지방계약", "지자체", "공기업", "준정부기관", "출자출연")
        if _compact(term) in compact
    ]
    if len(agency_terms) >= 2:
        reasons.append("multiple_agency_or_law_system_terms")

    if _has_any(user_message, ("그럼", "두번째", "두 번째", "앞에서", "위에서", "그 방법")):
        reasons.append("conversation_reference_needs_context")

    if _has_any(user_message, ("혼동", "충돌", "상충", "다른데", "비교", "차이")):
        reasons.append("comparison_or_conflict_question")

    return reasons


def assess_tool_loop_gate(
    *,
    user_message: str,
    query_tier: int,
    mandatory_mcp_plan: list[dict[str, Any]] | None = None,
    mandatory_mcp_executed: list[Any] | None = None,
    mandatory_mcp_missing: list[Any] | None = None,
    evidence_cards: list[dict[str, Any]] | None = None,
    practice_manual_cards: list[Any] | None = None,
    pps_qa_cards: list[Any] | None = None,
    routing_confidence: dict[str, Any] | None = None,
    gateway_route: str | None = None,
    has_amount: bool = False,
    route_plan: Any = None,
    evidence_coverage: Any = None,
) -> ToolLoopGateDecision:
    """Classify whether the prepared evidence is enough before LLM tool use.

    In ``shadow`` mode the decision is telemetry only.  ``enforce`` can be used
    later for QA-approved writer-only cases.
    """
    plan_count = len(mandatory_mcp_plan or [])
    executed_count = len(mandatory_mcp_executed or [])
    missing_count = len(mandatory_mcp_missing or [])
    practice_count = len(practice_manual_cards or [])
    pps_count = len(pps_qa_cards or [])
    evidence_hits, evidence_missing, internal_hits, covered = _evidence_counts(evidence_cards)
    expected = _expected_supports(user_message)
    coverage = _assess_coverage_if_possible(
        route_plan=route_plan,
        evidence_cards=evidence_cards,
        practice_manual_cards=practice_manual_cards,
        pps_qa_cards=pps_qa_cards,
        evidence_coverage=evidence_coverage,
    )
    coverage_status = str(_coverage_attr(coverage, "status", "not_checked") or "not_checked")
    coverage_score = float(_coverage_attr(coverage, "score", 0.0) or 0.0)
    required_topics = list(_coverage_attr(coverage, "required_topics", []) or [])
    covered_topics = list(_coverage_attr(coverage, "covered_topics", []) or [])
    partial_topics = list(_coverage_attr(coverage, "partial_topics", []) or [])
    missing_topics = list(_coverage_attr(coverage, "missing_topics", []) or [])
    coverage_expected_supports = list(_coverage_attr(coverage, "expected_supports", []) or [])
    for support in coverage_expected_supports:
        if support not in expected:
            expected.append(support)
    covered_expected = [label for label in expected if label in covered]
    missing_expected = [label for label in expected if label not in covered]

    reasons: list[str] = []
    blockers: list[str] = []

    if evidence_hits:
        reasons.append("precollected_evidence_hit")
    if internal_hits:
        reasons.append("internal_db_evidence_available")
    if practice_count:
        reasons.append("practice_manual_cards_available")
    if pps_count:
        reasons.append("pps_qa_cards_available")
    if gateway_route and gateway_route != "complex_router":
        reasons.append(f"front_gateway:{gateway_route}")

    if query_tier in (1, 2) and plan_count == 0:
        blockers.append("no_precollection_plan_for_legal_query")
    if plan_count and missing_count >= plan_count and executed_count == 0:
        blockers.append("all_precollection_failed")
    if expected and missing_expected and coverage_status != "sufficient" and not (practice_count or pps_count):
        blockers.append("expected_supports_not_covered")
    if coverage_status in {"partial", "insufficient"} and missing_topics:
        blockers.append("route_plan_evidence_topics_not_covered")
        reasons.append(f"evidence_coverage:{coverage_status}")
    elif coverage_status == "sufficient":
        reasons.append("route_plan_evidence_topics_covered")

    ambiguity_reasons = _semantic_ambiguity_reasons(user_message)
    for reason in ambiguity_reasons:
        if reason == "conversation_reference_needs_context":
            blockers.append(reason)
        elif reason in {"multiple_agency_or_law_system_terms", "comparison_or_conflict_question"}:
            if evidence_hits >= 2:
                reasons.append(f"{reason}_covered_by_multiple_evidence")
            else:
                blockers.append(reason)
        else:
            blockers.append(reason)

    if routing_confidence:
        level = routing_confidence.get("routing_confidence_level")
        ambiguous = bool(routing_confidence.get("routing_ambiguous"))
        if ambiguous or level == "low":
            blockers.append("low_or_ambiguous_routing_confidence")

    score = 0.0
    if evidence_hits:
        score += 0.35
    if internal_hits:
        score += 0.15
    if expected:
        score += 0.25 * (len(covered_expected) / len(expected))
    elif evidence_hits:
        score += 0.15
    if practice_count:
        score += 0.10
    if pps_count:
        score += 0.05
    if coverage is not None and coverage_status != "not_required":
        score += 0.20 * coverage_score
    if executed_count and not missing_count:
        score += 0.10
    if missing_count:
        score -= min(0.15, missing_count * 0.03)
    if ambiguity_reasons:
        score -= 0.10
    if has_amount and not evidence_hits:
        score -= 0.15
    score = max(0.0, min(1.0, round(score, 3)))

    can_use_writer_only = score >= 0.65 and not blockers
    if can_use_writer_only:
        recommendation = "writer_only_candidate"
        should_allow_loop = False
        reasons.append("evidence_sufficient_for_card_writer")
    elif evidence_hits or practice_count or pps_count:
        recommendation = "limited_loop_if_needed"
        should_allow_loop = True
        reasons.append("precollected_context_partial_or_ambiguous")
    else:
        recommendation = "tool_loop_needed"
        should_allow_loop = True
        reasons.append("precollected_context_insufficient")

    return ToolLoopGateDecision(
        recommendation=recommendation,
        evidence_sufficiency_score=score,
        should_allow_loop=should_allow_loop,
        can_use_writer_only=can_use_writer_only,
        reasons=reasons,
        blockers=list(dict.fromkeys(blockers)),
        expected_supports=expected,
        covered_supports=covered_expected,
        missing_supports=missing_expected,
        evidence_coverage_status=coverage_status,
        evidence_coverage_score=coverage_score,
        required_evidence_topics=required_topics,
        covered_evidence_topics=covered_topics,
        partial_evidence_topics=partial_topics,
        missing_evidence_topics=missing_topics,
        evidence_hit_count=evidence_hits,
        evidence_missing_count=evidence_missing,
        internal_db_hit_count=internal_hits,
        practice_manual_card_count=practice_count,
        pps_qa_card_count=pps_count,
    )
