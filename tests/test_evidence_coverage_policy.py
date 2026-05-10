from types import SimpleNamespace

from app.policies.evidence_coverage_policy import assess_evidence_coverage


def _card(*supports, status="hit", source="internal_db"):
    return {
        "status": status,
        "source": source,
        "supports": list(supports),
    }


def test_coverage_sufficient_when_route_plan_topics_are_supported():
    route_plan = SimpleNamespace(
        retrieval_needs=("legal_basis", "regional_support_catalog"),
        evidence_topics=(
            "direct_contract_thresholds",
            "mas_shopping_mall",
            "sme_competition_product",
            "innovation_or_technology_development_product",
            "regional_support_methods",
        ),
    )

    result = assess_evidence_coverage(
        route_plan=route_plan,
        evidence_cards=[
            _card("direct_contract", "amount_threshold"),
            _card("mas"),
            _card("sme_competition", "direct_production"),
            _card("innovation_product", "priority_purchase"),
            _card("regional_restriction"),
        ],
    )

    assert result.status == "sufficient"
    assert result.score == 1.0
    assert result.missing_topics == []


def test_coverage_partial_when_route_plan_alternative_route_is_missing():
    route_plan = SimpleNamespace(
        retrieval_needs=("legal_basis",),
        evidence_topics=("direct_contract_thresholds", "mas_shopping_mall"),
    )

    result = assess_evidence_coverage(
        route_plan=route_plan,
        evidence_cards=[_card("direct_contract", "amount_threshold")],
    )

    assert result.status == "partial"
    assert "mas_shopping_mall" in result.missing_topics
    assert result.score < 1.0
