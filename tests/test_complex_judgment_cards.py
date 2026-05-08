from app.policies.complex_judgment_cards import (
    build_complex_judgment_cards,
    render_complex_judgment_cards,
)


def test_complex_cards_combine_legal_route_catalog_and_candidate_sources():
    cards = build_complex_judgment_cards(
        user_message="LED 조명 8천만원으로 부산업체 활용 방법 알려줘",
        amount=80_000_000,
        item_name="LED 조명",
        contract_object="goods",
        agency_type="local_government",
        tool_results=[
            {
                "tool_name": "search_shopping_mall",
                "status": "success",
                "result": "부산 지역업체 검색 결과: 총 3건",
            },
            {
                "tool_name": "search_certified_product",
                "status": "success",
                "result": "검색 결과가 없습니다",
            },
        ],
        evidence_cards=[
            {
                "status": "hit",
                "source": "internal_db",
                "law_name": "지방계약법 시행령",
                "article_no": "제25조",
            }
        ],
    )

    card_types = {card["card_type"] for card in cards}
    assert "legal_basis" in card_types
    assert "purchase_route" in card_types
    assert "support_scheme" in card_types
    assert "candidate_source" in card_types
    assert any(card["status"] == "candidate_found" for card in cards)


def test_complex_cards_render_compact_context_for_llm():
    cards = build_complex_judgment_cards(
        user_message="8천만원 청소용역을 부산업체로 맡길 방법이 있어?",
        amount=80_000_000,
        item_name="청소용역",
        contract_object="service",
        agency_type="national_agency",
        tool_results=[],
        evidence_cards=[],
    )

    rendered = render_complex_judgment_cards(cards)
    assert "복합질문 판단 카드" in rendered
    assert "지역제한경쟁입찰" in rendered
    assert "일반 용역 소액수의" in rendered
