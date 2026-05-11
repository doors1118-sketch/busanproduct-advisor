from app.router.query_gateway import decide_query_gateway


def test_gateway_standard_card_sole_contract_threshold():
    result = decide_query_gateway("수의계약 한도와 1인 견적 기준 알려줘")

    assert result.route == "standard_card"
    assert result.confidence == "certain"
    assert result.matched_card_id == "sole_contract_threshold"
    assert result.exclusions == []


def test_gateway_vat_threshold_question_is_not_sole_contract_card():
    result = decide_query_gateway("수의계약 한도를 계산할 때 부가가치세를 포함해야 하나요, 제외해야 하나요?")

    assert result.route == "complex_router"
    assert result.reason == "no_certain_front_gate_match"
    assert result.matched_card_id is None
    assert result.llm_validation_required is True


def test_gateway_innovation_product_question_is_not_sole_contract_card():
    result = decide_query_gateway("혁신제품으로 지정된 부산 기업 제품은 금액 제한 없이 1인 수의계약이 가능한가요?")

    assert result.route == "complex_router"
    assert result.reason == "no_certain_front_gate_match"
    assert result.matched_card_id is None
    assert result.llm_validation_required is True


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


def test_gateway_pure_find_supplier_is_company_search():
    result = decide_query_gateway("냉난방기 부산업체 찾아줘")

    assert result.route == "company_search"


def test_gateway_does_not_company_search_for_generic_goods_word():
    result = decide_query_gateway("물품 부산업체 추천해줘")

    assert result.route == "complex_router"


def test_gateway_specific_item_amount_local_purchase_is_complex():
    result = decide_query_gateway("LED 조명 2억인데 부산업체 활용 방법 있어?")

    assert result.route == "complex_router"


def test_gateway_agency_law_conflict_is_not_company_search():
    result = decide_query_gateway(
        "국가기관이 컴퓨터 구매에서 부산 지역업체를 우대하고 싶을 때 지방계약 지역제한 기준을 그대로 쓰면 안 되지?"
    )

    assert result.route == "complex_router"
    assert result.reason == "agency_law_conflict_requires_legal_context"


def test_gateway_procurement_design_question_is_not_company_search():
    result = decide_query_gateway("청사 경비용역을 부산업체 중심으로 검토하려면 지역제한, 평가항목, 면허를 어떻게 봐야 해?")

    assert result.route == "complex_router"
    assert result.reason == "procurement_design_question_requires_context"


def test_gateway_regional_restriction_standard_card():
    result = decide_query_gateway("지역제한경쟁입찰 종합공사 기준금액 국가 지방 공기업 비교해줘")

    assert result.route == "standard_card"
    assert result.matched_card_id == "regional_restriction_construction_threshold"


def test_gateway_candidate_only_phrase_is_company_search():
    result = decide_query_gateway("CCTV 구매 절차 말고 업체 후보만 보고 싶어")

    assert result.route == "company_search"


def test_gateway_company_negative_is_not_company_search():
    result = decide_query_gateway("CCTV 부산업체 활용 방법 알려줘. 업체명 추천은 필요 없어")

    assert result.route == "complex_router"


def test_gateway_mas_local_supplier_choice_is_not_pure_company_search():
    result = decide_query_gateway("종합쇼핑몰에서 냉난방기 사면 부산업체 고를 수 있나?")

    assert result.route == "complex_router"
