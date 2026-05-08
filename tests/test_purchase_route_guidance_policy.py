from app.policies.purchase_route_guidance_policy import (
    build_purchase_route_cards,
    format_purchase_route_guidance_for_llm,
)


def _tool(tool_name: str, result: str) -> dict:
    return {"tool_name": tool_name, "status": "success", "result": result, "elapsed_ms": 1}


def test_80m_goods_marks_general_and_policy_one_quote_as_not_viable():
    cards = build_purchase_route_cards(
        amount=80_000_000,
        item_name="LED 조명",
        tool_results=[],
    )
    by_id = {card.route_id: card for card in cards}

    assert by_id["general_small_value_direct"].status == "not_viable"
    assert "2천만원" in by_id["general_small_value_direct"].user_label
    assert by_id["policy_company_one_quote"].status == "not_viable"
    assert "5천만원" in by_id["policy_company_one_quote"].user_label


def test_route_guidance_uses_company_tool_counts_as_candidates():
    tool_results = [
        _tool("search_shopping_mall", "부산 지역업체 검색 결과: 총 3건"),
        _tool("search_certified_product", "부산 지역업체 검색 결과: 총 2건"),
        _tool("search_innovation_product", "검색 결과가 없습니다. 다른 키워드로 검색해 보세요."),
    ]

    cards = build_purchase_route_cards(
        amount=80_000_000,
        item_name="LED 조명",
        tool_results=tool_results,
    )
    by_id = {card.route_id: card for card in cards}

    assert by_id["shopping_mall_mas"].user_label == "후보 3건"
    assert by_id["technology_development_product"].user_label == "후보 2건"
    assert by_id["innovation_product"].user_label == "후보 미확인"


def test_llm_guidance_explicitly_preserves_llm_practical_answer_role():
    context = format_purchase_route_guidance_for_llm(
        amount=80_000_000,
        item_name="LED 조명",
        agency_type="local_government",
        tool_results=[],
    )

    assert "최종 답변은 아래 경로를 조합해 실무형으로 작성" in context
    assert "가능 업체'가 아니라 '검토 후보" in context
    assert "일반 2천만원 소액수의 경로는 어려움" in context
    assert "5천만원 1인 견적 경로는 어려움" in context


def test_service_route_cards_focus_on_license_and_regional_service_company():
    tool_results = [
        _tool("search_local_company_by_license", "부산 지역업체 검색 결과: 총 4건"),
        _tool("search_company_by_policy", "부산 지역업체 검색 결과: 총 2건"),
    ]

    cards = build_purchase_route_cards(
        amount=80_000_000,
        item_name="청소용역",
        contract_object="service",
        tool_results=tool_results,
    )
    by_id = {card.route_id: card for card in cards}

    assert by_id["service_small_value_direct"].status == "not_viable"
    assert by_id["local_service_company"].user_label == "후보 4건"
    assert by_id["service_policy_candidate"].user_label == "후보 2건"


def test_construction_route_cards_include_regional_and_joint_contract_paths():
    context = format_purchase_route_guidance_for_llm(
        amount=200_000_000,
        item_name="전기공사",
        contract_object="construction",
        tool_results=[_tool("search_local_company_by_license", "부산 지역업체 검색 결과: 총 5건")],
    )

    assert "계약대상: 공사" in context
    assert "공사 지역제한 입찰" in context
    assert "지역의무공동도급/공동수급" in context
    assert "부산 공사업체 후보" in context
