from app.router.query_gateway import decide_query_gateway


def test_gateway_standard_card_sole_contract_threshold():
    result = decide_query_gateway("수의계약 한도와 1인 견적 기준 알려줘")

    assert result.route == "standard_card"
    assert result.confidence == "certain"
    assert result.matched_card_id == "sole_contract_threshold"
    assert result.exclusions == []


def test_gateway_amount_case_excludes_standard_card():
    result = decide_query_gateway("2억 물품 살 건데 수의계약 가능해?")

    assert result.route == "complex_router"
    assert "amount_case_question" in result.exclusions
    assert result.llm_validation_required is True


def test_gateway_direct_article_lookup():
    result = decide_query_gateway("지방계약법 시행령 제25조 설명해줘")

    assert result.route == "direct_article"
    assert result.law_query == "지방계약법 시행령 제25조"


def test_gateway_company_search_only_for_specific_item_without_amount_case():
    result = decide_query_gateway("CCTV 부산업체 추천해줘")

    assert result.route == "company_search"
    assert result.reason == "specific_item_company_lookup_without_amount_case"


def test_gateway_does_not_company_search_for_generic_goods_word():
    result = decide_query_gateway("물품 부산업체 추천해줘")

    assert result.route == "complex_router"


def test_gateway_specific_item_amount_local_purchase_is_complex():
    result = decide_query_gateway("LED 조명 2억인데 부산업체 활용 방법 있어?")

    assert result.route == "complex_router"


def test_gateway_regional_restriction_standard_card():
    result = decide_query_gateway("지역제한경쟁입찰 종합공사 기준금액 국가 지방 공기업 비교해줘")

    assert result.route == "standard_card"
    assert result.matched_card_id == "regional_restriction_construction_threshold"
