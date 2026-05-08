from app.policies.model_routing_policy import classify_query_tier
from app.router.intent_schema import RouterResult, RouterSlots


def _risk(level="low"):
    return {"risk_level": level}


def test_pure_legal_explanation_goes_to_tier_1_even_with_contract_keyword():
    router_result = RouterResult(
        primary_intent="legal_explanation",
        legal_explanation_only=True,
        legal_review_required=True,
        candidate_lookup_required=False,
        company_lookup_required=False,
        slots=RouterSlots(legal_topic="수의계약"),
    )

    tier = classify_query_tier(
        _risk("medium"),
        ["common_procurement"],
        "수의계약이 뭐야?",
        router_result,
    )

    assert tier == 1


def test_local_product_explanation_does_not_become_company_fast_track():
    router_result = RouterResult(
        primary_intent="legal_explanation",
        secondary_intents=["local_purchase_support"],
        legal_explanation_only=True,
        legal_review_required=True,
        local_purchase_support_required=True,
        candidate_lookup_required=False,
        company_lookup_required=False,
    )

    tier = classify_query_tier(
        _risk("low"),
        ["common_procurement"],
        "지역상품 우선구매가 뭐야?",
        router_result,
    )

    assert tier == 1


def test_specific_company_search_stays_tier_0():
    router_result = RouterResult(
        primary_intent="candidate_search",
        legal_explanation_only=False,
        candidate_lookup_required=True,
        company_lookup_required=True,
        slots=RouterSlots(item_name="LED", location="부산", local_supplier_intent=True),
    )

    tier = classify_query_tier(
        _risk("low"),
        ["company_search"],
        "LED 조명 부산 지역업체 있어?",
        router_result,
    )

    assert tier == 0


def test_agency_specific_question_still_tier_3():
    router_result = RouterResult(
        primary_intent="legal_explanation",
        legal_explanation_only=True,
        legal_review_required=True,
    )

    tier = classify_query_tier(
        _risk("high"),
        ["common_procurement"],
        "공기업 수의계약 기준이 뭐야?",
        router_result,
    )

    assert tier == 3
