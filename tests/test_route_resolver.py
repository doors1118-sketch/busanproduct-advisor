from types import SimpleNamespace

from app.prompting.keyword_pre_router import keyword_pre_route
from app.policies.model_routing_policy import generate_mandatory_mcp_plan
from app.router.intent_rag_resolver import resolve_intent_context
from app.router.route_resolver import build_intent_frame, resolve_route_plan


def test_route_resolver_turns_amount_item_question_into_multi_section_plan():
    question = "예산 6천만원으로 컴퓨터 구매하고 싶다. 계약 방법 안내해봐"
    keyword = keyword_pre_route(question)
    rag = resolve_intent_context(question)

    frame = build_intent_frame(
        question,
        keyword_result=keyword,
        intent_rag_decision=rag,
        intent_labels=[cat for cat in keyword.matched_categories if cat != "unclear"],
    )
    plan = resolve_route_plan(frame)

    assert frame.amount == 60_000_000
    assert frame.item_name == "컴퓨터"
    assert "contract_review" in frame.labels
    assert plan.query_tier == 2
    assert plan.execution_mode == "evidence_prefetch"
    assert "procurement_routes" in plan.answer_sections
    assert "legal_basis" in plan.retrieval_needs
    assert "amount_based_contract_route" in plan.evidence_topics
    assert "mas_shopping_mall" in plan.evidence_topics
    assert "sme_competition_product" in plan.evidence_topics
    assert "innovation_or_technology_development_product" in plan.evidence_topics
    assert plan.candidate_policy["include_route_relevant_only"] is True


def test_route_resolver_blocks_company_candidates_when_user_says_no_company_names():
    question = "CCTV 부산업체 활용 방법 알려줘. 업체명 추천은 필요 없어"
    keyword = keyword_pre_route(question)
    rag = resolve_intent_context(question)

    frame = build_intent_frame(
        question,
        keyword_result=keyword,
        intent_rag_decision=rag,
        intent_labels=[cat for cat in keyword.matched_categories if cat != "unclear"],
    )
    plan = resolve_route_plan(frame)

    assert frame.company_search_required is False
    assert frame.company_search_blocked is True
    assert "company_search" not in frame.labels
    assert plan.company_search_mode == "none"
    assert plan.execution_mode == "evidence_prefetch"
    assert "omit_company_candidates" in plan.negative_constraints
    assert "respect_user_request_to_exclude_company_names" in plan.quality_controls


def test_route_resolver_keeps_pure_company_lookup_fast():
    question = "CCTV 부산업체 후보만 보여줘"
    keyword = keyword_pre_route(question)
    rag = resolve_intent_context(question)

    frame = build_intent_frame(
        question,
        keyword_result=keyword,
        intent_rag_decision=rag,
        intent_labels=[cat for cat in keyword.matched_categories if cat != "unclear"],
    )
    plan = resolve_route_plan(frame)

    assert frame.company_search_required is True
    assert frame.company_search_only is True
    assert plan.query_tier == 0
    assert plan.execution_mode == "company_fast_track"
    assert plan.use_fast_track is True
    assert plan.company_search_mode == "candidates_only"
    assert plan.candidate_policy["candidate_table_purpose"] == "supplier lookup only, no legal conclusion"


def test_route_resolver_policy_performance_question_is_legal_not_company_search():
    question = "여성기업제품, 장애인기업제품을 구매해도 중소기업제품 구매실적에 포함이 되는지?"
    keyword = keyword_pre_route(question)
    rag = resolve_intent_context(question)

    frame = build_intent_frame(
        question,
        keyword_result=keyword,
        intent_rag_decision=rag,
        intent_labels=[cat for cat in keyword.matched_categories if cat != "unclear"],
    )
    plan = resolve_route_plan(frame)

    assert "legal_explanation" in frame.labels
    assert frame.company_search_required is False
    assert plan.query_tier == 1
    assert plan.execution_mode == "evidence_prefetch"
    assert "legal_basis" in plan.answer_sections
    assert "policy_company_purchase_performance" in plan.evidence_topics


def test_route_resolver_preserves_llm_adjudicator_slot_corrections():
    question = "장비 납품 설치 포함해서 발주하려면 물품이야 공사야?"
    keyword = keyword_pre_route(question)
    router_result = SimpleNamespace(
        primary_intent="contract_review",
        secondary_intents=["item_eligibility"],
        confidence=0.76,
        candidate_lookup_required=False,
        company_lookup_required=False,
        legal_review_required=True,
        local_purchase_support_required=False,
        slots=SimpleNamespace(item_name="장비", contract_object="goods"),
    )

    frame = build_intent_frame(
        question,
        keyword_result=keyword,
        router_result=router_result,
        intent_labels=[cat for cat in keyword.matched_categories if cat != "unclear"],
    )
    plan = resolve_route_plan(frame)

    assert "mixed_contract_object" in frame.conflicts
    assert "goods" in frame.contract_object_candidates
    assert "construction" in frame.contract_object_candidates
    assert plan.query_tier == 2
    assert plan.execution_mode == "evidence_prefetch"
    assert "legal_basis" in plan.retrieval_needs
    assert "mixed_contract_object" in plan.evidence_topics
    assert "avoid_single_contract_object_assumption" in plan.quality_controls


def test_mcp_plan_generation_respects_route_plan_no_legal_need():
    route_plan = SimpleNamespace(
        execution_mode="practice_guided",
        retrieval_needs=("practice_manual",),
    )

    plan = generate_mandatory_mcp_plan(
        "물품 구매 절차만 간단히 알려줘",
        1,
        agency_type="default",
        route_plan=route_plan,
    )

    assert plan == []


def test_mcp_plan_generation_uses_route_plan_evidence_topics_as_seed():
    route_plan = SimpleNamespace(
        execution_mode="evidence_prefetch",
        retrieval_needs=("legal_basis", "regional_support_catalog", "item_eligibility"),
        evidence_topics=(
            "amount_based_contract_route",
            "direct_contract_thresholds",
            "mas_shopping_mall",
            "innovation_or_technology_development_product",
            "regional_support_methods",
            "item_eligibility",
        ),
    )

    plan = generate_mandatory_mcp_plan(
        "컴퓨터 구매 방법 알려줘",
        1,
        agency_type="default",
        route_plan=route_plan,
    )
    queries = [(item["name"], item["args"]["query"]) for item in plan]
    reasons = [item.get("selected_reason", "") for item in plan]

    assert ("search_law", "지방계약법 시행령 제25조") in queries
    assert ("search_admin_rule", "물품 다수공급자계약 업무처리규정") in queries
    assert ("search_admin_rule", "혁신제품 구매 운영 규정") in queries
    assert ("search_law", "중소기업제품 구매촉진 및 판로지원법 제6조") in queries
    assert any(reason.startswith("route_plan:") for reason in reasons)


def test_mcp_plan_generation_prioritizes_route_plan_seed_items():
    route_plan = SimpleNamespace(
        execution_mode="evidence_prefetch",
        retrieval_needs=("legal_basis", "item_eligibility"),
        evidence_topics=(
            "amount_based_contract_route",
            "direct_contract_thresholds",
            "mas_shopping_mall",
            "sme_competition_product",
            "innovation_or_technology_development_product",
        ),
    )

    plan = generate_mandatory_mcp_plan(
        "예산 6천만원으로 컴퓨터 구매하고 싶다. 계약 방법 안내해봐",
        2,
        agency_type="default",
        route_plan=route_plan,
    )
    reasons = [item.get("selected_reason", "") for item in plan[:8]]

    assert any(reason == "route_plan:direct_contract_thresholds" for reason in reasons)
    assert any(reason.startswith("route_plan:mas_shopping_mall") for reason in reasons)


def test_route_plan_keeps_explicit_route_comparison_narrow():
    question = "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?"

    frame = build_intent_frame(question)
    plan = resolve_route_plan(frame)
    mcp_plan = generate_mandatory_mcp_plan(
        question,
        plan.query_tier,
        agency_type="default",
        route_plan=plan,
    )
    queries = [item["args"]["query"] for item in mcp_plan]

    assert frame.item_name == "노트북"
    assert frame.amount == 45_000_000
    assert plan.company_search_mode == "route_relevant_candidates"
    assert "company_candidates" in plan.retrieval_needs
    assert "purchase_intent_implies_route_relevant_candidates" in plan.reasons
    assert "include_legal_basis_for_each_purchase_route" in plan.quality_controls
    assert "mas_shopping_mall" in plan.evidence_topics
    assert "innovation_or_technology_development_product" not in plan.evidence_topics
    assert len(mcp_plan) <= 11
    assert "지방계약법 시행령 제25조" in queries
    assert "물품 다수공급자계약 업무처리규정" in queries


def test_route_plan_ignores_llm_local_support_without_local_signal():
    question = "노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?"
    router_result = SimpleNamespace(
        primary_intent="contract_review",
        secondary_intents=["local_purchase_support", "procurement_route_review"],
        confidence=0.72,
        candidate_lookup_required=False,
        company_lookup_required=False,
        legal_review_required=True,
        local_purchase_support_required=True,
        slots=SimpleNamespace(item_name="노트북", contract_object="goods", amount=45_000_000),
    )

    frame = build_intent_frame(question, router_result=router_result)
    plan = resolve_route_plan(frame)

    assert frame.local_purchase_support_required is False
    assert "local_purchase_support" not in frame.labels
    assert plan.company_search_mode == "route_relevant_candidates"
    assert "regional_support_catalog" not in plan.retrieval_needs
    assert "regional_support_methods" not in plan.evidence_topics


def test_route_plan_exposes_evidence_topics_for_regional_mas_and_innovation_routes():
    question = "종합쇼핑몰에서 혁신제품 컴퓨터를 부산업체로 구매할 방법과 근거 알려줘"
    keyword = keyword_pre_route(question)
    rag = resolve_intent_context(question)

    frame = build_intent_frame(
        question,
        keyword_result=keyword,
        intent_rag_decision=rag,
        intent_labels=[cat for cat in keyword.matched_categories if cat != "unclear"],
    )
    plan = resolve_route_plan(frame)

    assert "mas_shopping_mall" in plan.evidence_topics
    assert "innovation_or_technology_development_product" in plan.evidence_topics
    assert "regional_support_methods" in plan.evidence_topics
    assert "legal_basis" in plan.retrieval_needs
