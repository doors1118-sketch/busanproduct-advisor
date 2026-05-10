from app.policies.answer_builder_policy import build_simple_company_search_answer


def test_simple_company_search_answer_mentions_search_item_on_no_results():
    meta = {"company_search_query": "냉난방기"}
    answer = build_simple_company_search_answer(meta, has_candidates=False)

    assert "냉난방기" in answer
    assert "유효한 업체 후보를 추출하지 못했습니다" in answer


def test_simple_company_search_answer_compacts_long_search_item_label():
    meta = {"company_search_query": "냉난방기 는 MAS로 처리할 수 있는지, 고려는 하는지 알려줘"}
    answer = build_simple_company_search_answer(meta, has_candidates=False)

    assert "냉난방기 기준" in answer
    assert "MAS로 처리할 수 있는지" not in answer
