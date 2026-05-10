from app.policies.practice_manual_cards import (
    format_practice_manual_cards_for_llm,
    is_contract_procedure_query,
    match_contract_lifecycle_cards,
    match_practice_manual_cards,
    render_contract_lifecycle_for_answer,
)


def test_practice_manual_cards_match_complex_purchase_question():
    cards = match_practice_manual_cards(
        "8천만원으로 LED 조명을 사려고 한다. 부산업체 활용 방법 알려줘.",
        contract_object="goods",
        agency_type="local_government",
    )
    topics = {card["topic"] for card in cards}

    assert cards
    assert "direct_contract" in topics
    assert "regional_restriction" in topics or "local_company_points" in topics
    assert all(card["numeric_use_allowed"] is False for card in cards)


def test_practice_manual_context_warns_against_numeric_use():
    cards = match_practice_manual_cards("지역제한경쟁입찰 기준 알려줘", contract_object="construction")
    rendered = format_practice_manual_cards_for_llm(cards)

    assert "실무 매뉴얼 카드" in rendered
    assert "source map resolved_value" in rendered
    assert "매뉴얼 카드의 숫자 표현은 답변의 현재 기준값으로 사용하지 마세요" in rendered


def test_practice_manual_cards_prioritize_lifecycle_flow_questions():
    cards = match_practice_manual_cards(
        "공공계약 절차를 처음부터 끝까지 흐름으로 설명해줘",
        contract_object="service",
        max_cards=5,
    )
    assert cards
    assert any(card.get("flow_stage") for card in cards)
    assert any(str(card["topic"]).startswith("lifecycle_") for card in cards)


def test_practice_manual_cards_prioritize_concept_questions():
    cards = match_practice_manual_cards(
        "추정가격 예정가격 기초금액 차이가 뭐야?",
        contract_object="goods",
        max_cards=5,
    )
    assert cards
    assert any(card.get("topic") == "concept_price_terms" for card in cards)
    assert all(card["numeric_use_allowed"] is False for card in cards)


def test_contract_procedure_query_uses_ordered_lifecycle_cards():
    assert is_contract_procedure_query("물품을 구매하려고 한다. 구매 절차를 안내해줘")

    cards = match_contract_lifecycle_cards(
        "물품을 구매하려고 한다. 구매 절차를 안내해줘",
        contract_object="goods",
    )

    assert len(cards) >= 10
    assert cards[0]["topic"] == "lifecycle_planning_budget"
    assert cards[-1]["stage_order"] >= cards[0]["stage_order"]
    assert all(card["numeric_use_allowed"] is False for card in cards)


def test_contract_lifecycle_render_separates_procedure_from_legal_judgment():
    cards = match_contract_lifecycle_cards(
        "물품 구매 절차를 처음부터 끝까지 알려줘",
        contract_object="goods",
    )
    rendered = render_contract_lifecycle_for_answer(cards, contract_object="goods")

    assert "물품 계약 절차 흐름" in rendered
    assert "기본계획 수립" in rendered
    assert "계약방법 결정" in rendered
    assert "법령/source map으로 따로 검증할 지점" in rendered
    assert "source map resolved_value" in rendered
    assert "중소기업자간 경쟁제품" in rendered
