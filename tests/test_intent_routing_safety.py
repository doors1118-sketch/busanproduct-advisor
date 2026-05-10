from app.policies.model_routing_policy import classify_query_tier
from app.prompting.guardrail_sanity_check import apply_guardrail_sanity_check
from app.prompting.keyword_pre_router import keyword_pre_route
from app.router.intent_schema import RouterResult, RouterSlots


def _risk(level: str = "low") -> dict:
    return {"risk_level": level}


def test_local_supplier_strategy_is_not_company_lookup():
    result = keyword_pre_route("용역계약에 있어 지역업체 참여가 가능한 방법은?")

    assert "service_contract" in result.matched_categories
    assert "local_purchase_support" in result.matched_categories
    assert "company_search" not in result.matched_categories
    assert "company_search" not in result.forced_guardrails


def test_amount_local_supplier_strategy_keeps_contract_review():
    result = keyword_pre_route("8천만원 청소용역을 부산 지역업체로 계약하려면 어떤 제도를 검토해야 해?")

    assert "service_contract" in result.matched_categories
    assert "local_purchase_support" in result.matched_categories
    assert "contract_review" in result.matched_categories
    assert "company_search" not in result.matched_categories


def test_specific_company_lookup_still_forces_company_search():
    result = keyword_pre_route("CCTV 부산업체 후보 추천해줘")

    assert "company_search" in result.matched_categories
    assert "company_search" in result.forced_guardrails


def test_sanity_check_does_not_add_company_search_for_procurement_design():
    guardrails = apply_guardrail_sanity_check(
        "청소용역을 부산 지역업체 중심으로 발주하려면 지역제한과 평가항목을 어떻게 봐야 해?",
        ["common_procurement", "service_contract"],
    )

    assert "company_search" not in guardrails
    assert "common_procurement" in guardrails
    assert "service_contract" in guardrails


def test_sanity_check_adds_company_search_for_explicit_candidate_lookup():
    guardrails = apply_guardrail_sanity_check(
        "CCTV 부산업체 후보 추천해줘",
        ["common_procurement", "item_purchase"],
    )

    assert "company_search" in guardrails


def test_model_tier_does_not_fast_track_local_support_strategy():
    router_result = RouterResult(
        primary_intent="local_purchase_support",
        legal_explanation_only=False,
        legal_review_required=True,
        local_purchase_support_required=True,
        candidate_lookup_required=False,
        company_lookup_required=False,
        slots=RouterSlots(service_type="청소용역", location="부산", local_supplier_intent=True),
    )

    tier = classify_query_tier(
        _risk("low"),
        ["common_procurement"],
        "용역계약에 있어 지역업체 참여가 가능한 방법은?",
        router_result,
    )

    assert tier == 1


def test_model_tier_keeps_explicit_candidate_lookup_fast():
    router_result = RouterResult(
        primary_intent="candidate_search",
        legal_explanation_only=False,
        candidate_lookup_required=True,
        company_lookup_required=True,
        slots=RouterSlots(item_name="CCTV", location="부산", local_supplier_intent=True),
    )

    tier = classify_query_tier(
        _risk("low"),
        ["company_search"],
        "CCTV 부산업체 후보 추천해줘",
        router_result,
    )

    assert tier == 0
