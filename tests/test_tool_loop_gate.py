import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from policies.tool_loop_gate import assess_tool_loop_gate


def _card(*supports, source="internal_db", status="hit"):
    return {
        "status": status,
        "source": source,
        "supports": list(supports),
    }


def test_writer_only_candidate_when_internal_evidence_covers_expected_supports():
    decision = assess_tool_loop_gate(
        user_message="지역제한경쟁입찰 기준 금액 알려줘",
        query_tier=2,
        mandatory_mcp_plan=[{"name": "search_law", "args": {"query": "지방계약법 시행령 제20조"}}],
        mandatory_mcp_executed=["search_law:지방계약법 시행령 제20조"],
        mandatory_mcp_missing=[],
        evidence_cards=[_card("regional_restriction", "amount_threshold")],
        practice_manual_cards=[],
        pps_qa_cards=[],
        routing_confidence={"routing_confidence_level": "high", "routing_ambiguous": False},
        gateway_route="complex_router",
        has_amount=True,
    )

    assert decision.recommendation == "writer_only_candidate"
    assert decision.can_use_writer_only is True
    assert decision.should_allow_loop is False
    assert decision.blockers == []


def test_partial_evidence_keeps_loop_available_instead_of_forcing_writer_only():
    decision = assess_tool_loop_gate(
        user_message="혁신제품이면 금액 제한 없이 수의계약과 우선구매가 가능한지 알려줘",
        query_tier=2,
        mandatory_mcp_plan=[{"name": "search_admin_rule", "args": {"query": "혁신제품 구매 운영 규정"}}],
        mandatory_mcp_executed=["search_admin_rule:혁신제품 구매 운영 규정"],
        mandatory_mcp_missing=[],
        evidence_cards=[_card("priority_purchase")],
        practice_manual_cards=[],
        pps_qa_cards=[],
        routing_confidence={"routing_confidence_level": "high", "routing_ambiguous": False},
        gateway_route="complex_router",
        has_amount=True,
    )

    assert decision.recommendation == "limited_loop_if_needed"
    assert decision.should_allow_loop is True
    assert "direct_contract" in decision.missing_supports


def test_comparison_question_can_still_be_writer_only_when_multiple_evidence_cards_exist():
    decision = assess_tool_loop_gate(
        user_message="국가기관 지역제한경쟁입찰과 지방계약 기준 차이를 비교해줘",
        query_tier=2,
        mandatory_mcp_plan=[
            {"name": "search_law", "args": {"query": "국가계약법 시행령 제21조"}},
            {"name": "search_law", "args": {"query": "지방계약법 시행령 제20조"}},
        ],
        mandatory_mcp_executed=[
            "search_law:국가계약법 시행령 제21조",
            "search_law:지방계약법 시행령 제20조",
        ],
        mandatory_mcp_missing=[],
        evidence_cards=[
            _card("regional_restriction"),
            _card("regional_restriction"),
        ],
        practice_manual_cards=[],
        pps_qa_cards=[],
        routing_confidence={"routing_confidence_level": "high", "routing_ambiguous": False},
        gateway_route="complex_router",
        has_amount=False,
    )

    assert decision.recommendation == "writer_only_candidate"
    assert decision.blockers == []
    assert any("covered_by_multiple_evidence" in reason for reason in decision.reasons)


def test_route_plan_missing_topic_keeps_loop_available_even_with_some_evidence():
    decision = assess_tool_loop_gate(
        user_message="6천만원 컴퓨터 구매 방법과 종합쇼핑몰 가능성을 알려줘",
        query_tier=2,
        mandatory_mcp_plan=[
            {"name": "search_law", "args": {"query": "지방계약법 시행령 제25조"}},
            {"name": "search_admin_rule", "args": {"query": "물품 다수공급자계약 업무처리규정"}},
        ],
        mandatory_mcp_executed=["search_law:지방계약법 시행령 제25조"],
        mandatory_mcp_missing=[],
        evidence_cards=[_card("direct_contract", "amount_threshold")],
        practice_manual_cards=[],
        pps_qa_cards=[],
        routing_confidence={"routing_confidence_level": "high", "routing_ambiguous": False},
        gateway_route="complex_router",
        has_amount=True,
        route_plan=type("RoutePlan", (), {
            "retrieval_needs": ("legal_basis",),
            "evidence_topics": ("direct_contract_thresholds", "mas_shopping_mall"),
        })(),
    )

    assert decision.recommendation == "limited_loop_if_needed"
    assert decision.should_allow_loop is True
    assert "route_plan_evidence_topics_not_covered" in decision.blockers
    assert "mas_shopping_mall" in decision.missing_evidence_topics


def test_all_precollection_failed_requires_tool_loop_or_fail_closed_path():
    decision = assess_tool_loop_gate(
        user_message="2억 물품 수의계약 가능해?",
        query_tier=2,
        mandatory_mcp_plan=[{"name": "search_law", "args": {"query": "지방계약법 시행령 제25조"}}],
        mandatory_mcp_executed=[],
        mandatory_mcp_missing=["search_law:지방계약법 시행령 제25조 (failed)"],
        evidence_cards=[_card(status="miss", source="missing")],
        practice_manual_cards=[],
        pps_qa_cards=[],
        routing_confidence={"routing_confidence_level": "high", "routing_ambiguous": False},
        gateway_route="complex_router",
        has_amount=True,
    )

    assert decision.recommendation == "tool_loop_needed"
    assert decision.should_allow_loop is True
    assert "all_precollection_failed" in decision.blockers
