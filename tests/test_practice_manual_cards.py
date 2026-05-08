from app.policies.practice_manual_cards import (
    format_practice_manual_cards_for_llm,
    match_practice_manual_cards,
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
