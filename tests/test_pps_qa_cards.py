from app.policies import pps_qa_cards


def test_pps_qa_cards_skip_non_procurement_query(monkeypatch):
    monkeypatch.setattr(pps_qa_cards, "load_pps_qa_rows", lambda: [
        {"title": "수의계약 해석", "question": "수의계약", "answer": "회신", "category": "계약"}
    ])

    assert pps_qa_cards.match_pps_qa_cards("오늘 날씨 알려줘") == []


def test_pps_qa_cards_return_practice_interpretation_only(monkeypatch):
    monkeypatch.setattr(pps_qa_cards, "load_pps_qa_rows", lambda: [
        {
            "title": "지역제한입찰 관련 해석질의",
            "question": "지역제한경쟁입찰 가능 여부 질의",
            "answer": "국가기관이 당사자가 되는 입찰에서 제한경쟁입찰의 적용 여부는 관련 규정과 발주 조건을 종합 검토해야 합니다.",
            "category": "입찰 및 낙찰자선정 > 입찰방법",
            "date": "2025-06-16",
            "public_no": "12345",
            "views": 10,
        }
    ])

    cards = pps_qa_cards.match_pps_qa_cards("지역제한경쟁입찰 기준 알려줘")

    assert len(cards) == 1
    assert cards[0]["source_status"] == "pps_qa_internal_db"
    assert cards[0]["use_scope"] == "practice_interpretation_only"
    assert "source_map resolved_value" in cards[0]["priority_note"]


def test_pps_qa_context_warns_not_to_override_law_or_amounts():
    context = pps_qa_cards.format_pps_qa_cards_for_llm([
        {
            "title": "수의계약 해석",
            "date": "2025-06-16",
            "category": "계약",
            "answer_excerpt": "수의계약 여부는 관련 규정을 확인해야 합니다.",
        }
    ])

    assert "실무 해석 보조자료" in context
    assert "금액·조문·시행일·법적 결론" in context
    assert "내부 법령 DB" in context
    assert "source_map resolved_value" in context
