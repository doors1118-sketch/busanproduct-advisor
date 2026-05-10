"""Evidence coverage checks for RoutePlan-driven retrieval.

The coverage checker answers a narrow question: did the preflight evidence
cards cover the legal/practical topics that RoutePlan said were required?
It does not generate answers and it does not call external tools.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


TOPIC_SUPPORT_RULES: dict[str, tuple[str, ...]] = {
    "amount_based_contract_route": ("direct_contract", "amount_threshold", "legal_principle"),
    "direct_contract_thresholds": ("direct_contract", "amount_threshold"),
    "regional_support_methods": ("regional_restriction", "local_company_point", "joint_contract", "priority_purchase"),
    "regional_restriction_or_local_points": ("regional_restriction", "local_company_point", "joint_contract"),
    "mas_shopping_mall": ("mas",),
    "mas_second_stage_competition": ("mas_second_stage", "mas"),
    "sme_competition_product": ("sme_competition", "direct_production", "item_eligibility"),
    "item_eligibility": ("sme_competition", "direct_production", "priority_purchase", "goods"),
    "innovation_or_technology_development_product": (
        "innovation_product",
        "tech_development_product",
        "priority_purchase",
        "direct_contract",
    ),
    "policy_company_purchase_performance": ("purchase_performance", "policy_company", "priority_purchase"),
    "mixed_contract_object": ("mixed_contract", "goods", "service", "construction"),
    "agency_law_scope_conflict": ("agency_scope", "regional_restriction", "legal_principle"),
    "split_procurement_review": ("split_procurement", "direct_contract"),
    "construction_period_extension": ("construction_period_extension",),
    "indirect_cost_review": ("indirect_cost",),
    "procurement_lifecycle_procedure": ("procedure",),
}

TOPIC_REQUIRED_ANY_COUNT: dict[str, int] = {
    "amount_based_contract_route": 2,
    "direct_contract_thresholds": 2,
    "regional_support_methods": 1,
    "regional_restriction_or_local_points": 1,
    "mas_shopping_mall": 1,
    "mas_second_stage_competition": 1,
    "sme_competition_product": 1,
    "item_eligibility": 1,
    "innovation_or_technology_development_product": 1,
    "policy_company_purchase_performance": 1,
    "mixed_contract_object": 1,
    "agency_law_scope_conflict": 1,
    "split_procurement_review": 1,
    "construction_period_extension": 1,
    "indirect_cost_review": 1,
    "procurement_lifecycle_procedure": 1,
}


@dataclass(frozen=True)
class EvidenceCoverageResult:
    status: str = "not_required"  # sufficient | partial | insufficient | not_required
    score: float = 1.0
    required_topics: list[str] = field(default_factory=list)
    covered_topics: list[str] = field(default_factory=list)
    partial_topics: list[str] = field(default_factory=list)
    missing_topics: list[str] = field(default_factory=list)
    expected_supports: list[str] = field(default_factory=list)
    covered_supports: list[str] = field(default_factory=list)
    missing_supports: list[str] = field(default_factory=list)
    evidence_hit_count: int = 0
    evidence_missing_count: int = 0
    reasons: list[str] = field(default_factory=list)

    def to_meta(self) -> dict[str, Any]:
        return {f"evidence_coverage_{key}": value for key, value in asdict(self).items()}


def _route_plan_topics(route_plan: Any) -> list[str]:
    return [str(topic) for topic in (getattr(route_plan, "evidence_topics", None) or []) if str(topic)]


def _route_plan_needs(route_plan: Any, *needs: str) -> bool:
    values = set(str(value) for value in (getattr(route_plan, "retrieval_needs", None) or []))
    return any(need in values for need in needs)


def _card_supports(evidence_cards: list[dict[str, Any]] | None) -> tuple[set[str], int, int]:
    supports: set[str] = set()
    hits = 0
    missing = 0
    for card in evidence_cards or []:
        if card.get("status") == "hit":
            hits += 1
            supports.update(str(item) for item in (card.get("supports") or []))
            supports.update(str(item) for item in (card.get("applicability") or []))
        else:
            missing += 1
    return supports, hits, missing


def assess_evidence_coverage(
    *,
    route_plan: Any = None,
    evidence_cards: list[dict[str, Any]] | None = None,
    practice_manual_cards: list[Any] | None = None,
    pps_qa_cards: list[Any] | None = None,
) -> EvidenceCoverageResult:
    topics = _route_plan_topics(route_plan)
    legal_topics = [topic for topic in topics if topic in TOPIC_SUPPORT_RULES]
    if not legal_topics and not _route_plan_needs(route_plan, "legal_basis", "regional_support_catalog"):
        return EvidenceCoverageResult(reasons=["no_route_plan_legal_evidence_required"])

    covered_supports_set, hit_count, missing_count = _card_supports(evidence_cards)
    if practice_manual_cards:
        covered_supports_set.add("procedure")
    if pps_qa_cards:
        covered_supports_set.add("interpretation")

    expected_supports: list[str] = []
    covered_topics: list[str] = []
    partial_topics: list[str] = []
    missing_topics: list[str] = []
    reasons: list[str] = []

    for topic in legal_topics:
        expected = TOPIC_SUPPORT_RULES.get(topic, ())
        for support in expected:
            if support not in expected_supports:
                expected_supports.append(support)

        matched = [support for support in expected if support in covered_supports_set]
        required_count = TOPIC_REQUIRED_ANY_COUNT.get(topic, 1)
        if len(matched) >= required_count:
            covered_topics.append(topic)
        elif matched:
            partial_topics.append(topic)
            reasons.append(f"partial:{topic}:{','.join(matched)}")
        else:
            missing_topics.append(topic)
            reasons.append(f"missing:{topic}")

    covered_supports = [support for support in expected_supports if support in covered_supports_set]
    missing_supports = [support for support in expected_supports if support not in covered_supports_set]

    total = len(legal_topics)
    if total == 0:
        score = 1.0 if hit_count else 0.0
    else:
        score = (len(covered_topics) + 0.5 * len(partial_topics)) / total
    score = round(max(0.0, min(1.0, score)), 3)

    if not legal_topics:
        status = "not_required"
    elif missing_topics:
        status = "partial" if covered_topics or partial_topics else "insufficient"
    elif partial_topics:
        status = "partial"
    else:
        status = "sufficient"

    if hit_count:
        reasons.append("evidence_cards_available")
    if missing_count:
        reasons.append("some_evidence_cards_missing")

    return EvidenceCoverageResult(
        status=status,
        score=score,
        required_topics=legal_topics,
        covered_topics=covered_topics,
        partial_topics=partial_topics,
        missing_topics=missing_topics,
        expected_supports=expected_supports,
        covered_supports=covered_supports,
        missing_supports=missing_supports,
        evidence_hit_count=hit_count,
        evidence_missing_count=missing_count,
        reasons=list(dict.fromkeys(reasons)),
    )
