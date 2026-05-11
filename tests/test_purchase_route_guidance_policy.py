from app.policies.purchase_route_guidance_policy import (
    build_purchase_route_cards,
    derive_candidate_table_display_options,
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
    assert by_id["general_small_value_direct"].route_priority == "excluded"
    assert by_id["policy_company_one_quote"].status == "not_viable"
    assert "5천만원" in by_id["policy_company_one_quote"].user_label
    assert by_id["policy_company_one_quote"].display_policy == "brief"


def test_60m_computer_prefers_two_quote_mas_and_hides_policy_table():
    cards = build_purchase_route_cards(
        amount=60_000_000,
        item_name="컴퓨터",
        contract_object="goods",
        tool_results=[
            _tool("search_shopping_mall", "부산 지역업체 검색 결과: 총 3건"),
            _tool("search_local_company_by_product", "부산 지역업체 검색 결과: 총 4건"),
            _tool("search_company_by_policy", "부산 지역업체 검색 결과: 총 5건"),
        ],
    )
    by_id = {card.route_id: card for card in cards}
    options = derive_candidate_table_display_options(cards)

    assert by_id["general_small_value_direct"].route_priority == "excluded"
    assert by_id["two_quote_small_value"].route_priority == "primary"
    assert by_id["shopping_mall_mas"].route_priority == "primary"
    assert by_id["sme_competition_direct_production"].route_priority == "reference"
    assert by_id["policy_company_one_quote"].route_priority == "excluded"
    assert "policy_company" in options["hidden_candidate_types"]
    assert "shopping_mall_supplier" in options["preferred_candidate_order"]

    context = format_purchase_route_guidance_for_llm(
        amount=60_000_000,
        item_name="컴퓨터",
        contract_object="goods",
        tool_results=[],
    )
    assert context.index("| 1순위 | 종합쇼핑몰(MAS) 직접구매 |") < context.index("| 2순위 | 지역제한 2인견적 |")
    assert "| 제외 | 정책기업 1인견적 | 5천만원 초과 |" in context


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


def test_45m_notebook_marks_policy_two_quote_and_mas_direct_check():
    cards = build_purchase_route_cards(
        amount=45_000_000,
        item_name="노트북",
        contract_object="goods",
        tool_results=[],
    )
    by_id = {card.route_id: card for card in cards}

    assert by_id["policy_company_one_quote"].route_priority == "primary"
    assert by_id["two_quote_small_value"].route_priority == "primary"
    assert by_id["general_small_value_direct"].route_priority == "excluded"
    assert "2천만원" in by_id["general_small_value_direct"].user_label

    mas = by_id["shopping_mall_mas"]
    assert mas.status == "mas_direct_check"
    assert mas.user_label == "2단계 기준 미만"
    assert mas.route_priority == "secondary"
    assert "노트북" in mas.practical_meaning
    assert "5천만원" in mas.practical_meaning
    assert "1억원" in mas.practical_meaning

    context = format_purchase_route_guidance_for_llm(
        amount=45_000_000,
        item_name="노트북",
        contract_object="goods",
        tool_results=[],
    )
    assert context.index("| 1순위 | 정책기업 1인견적 |") < context.index("| 2순위 | 지역제한 2인견적 |")
    assert context.index("| 2순위 | 지역제한 2인견적 |") < context.index("| 3순위 | 종합쇼핑몰(MAS) 직접구매 |")
    assert "지방계약법 시행령 제25조" in context
    assert "지방계약법 시행령 제30조" in context
    assert "물품 다수공급자계약 2단계경쟁 업무처리기준" in context


def test_policy_company_one_quote_is_not_always_first_below_general_one_quote_limit():
    cards = build_purchase_route_cards(
        amount=10_000_000,
        item_name="노트북",
        contract_object="goods",
        tool_results=[],
    )
    by_id = {card.route_id: card for card in cards}

    assert by_id["general_small_value_direct"].route_priority == "primary"
    assert by_id["policy_company_one_quote"].route_priority == "secondary"
    assert "최우선 경로는 아닙니다" in by_id["policy_company_one_quote"].practical_meaning

    context = format_purchase_route_guidance_for_llm(
        amount=10_000_000,
        item_name="노트북",
        contract_object="goods",
        tool_results=[],
    )
    assert context.index("| 1순위 | 일반 1인견적 |") < context.index("| 2순위 | 정책기업 1인견적 |")


def test_purchase_route_guidance_requires_legal_basis_per_visible_route():
    context = format_purchase_route_guidance_for_llm(
        amount=45_000_000,
        item_name="노트북",
        contract_object="goods",
        tool_results=[],
    )
    route_rows = [
        line
        for line in context.splitlines()
        if line.startswith("| ") and not line.startswith("| 순위") and not line.startswith("|---")
    ]

    assert route_rows
    for row in route_rows:
        cells = [cell.strip() for cell in row.strip("|").split("|")]
        assert len(cells) == 5
        assert cells[3]
        assert cells[3] != "확인 필요"
    assert "구매경로 판단에는 경로별 법적 근거를 반드시 함께 제시" in context
    assert "업체 후보표는 해당 경로의 근거 뒤에 붙인다" in context


def test_llm_guidance_explicitly_preserves_llm_practical_answer_role():
    context = format_purchase_route_guidance_for_llm(
        amount=80_000_000,
        item_name="LED 조명",
        agency_type="local_government",
        tool_results=[],
    )

    assert "최종 답변은 아래 경로를 조합해 실무형으로 작성" in context
    assert "가능 업체'가 아니라 '검토 후보" in context
    assert "일반 1인견적" in context
    assert "2천만원 초과" in context
    assert "정책기업 1인견적" in context
    assert "5천만원 초과" in context
    assert "법적 근거" in context
    assert "후보표는 구매경로 판단과 맞는 표만 사용" in context


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
    assert by_id["service_two_quote_small_value"].route_priority == "primary"
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
    assert "공사 지역제한" in context
    assert "지역의무공동도급" in context
    assert "부산 공사업체 후보" in context
    assert "공종별 수의계약 한도 확인 필요" in context
