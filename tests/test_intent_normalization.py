from app.router.intent_normalization import normalize_query_intent


def test_normalization_blocks_explicit_company_negative():
    norm = normalize_query_intent("지역업체 참여 방법 알려줘. 업체명 추천은 필요 없어")

    assert norm.local_support_requested is True
    assert norm.company_lookup_requested is False
    assert norm.company_lookup_blocked is True
    assert norm.legal_basis_requested is False


def test_normalization_candidate_only_overrides_procedure_terms():
    norm = normalize_query_intent("CCTV 구매 절차 말고 업체 후보만 보고 싶어")

    assert norm.item_name == "CCTV"
    assert norm.company_lookup_requested is True
    assert norm.company_lookup_blocked is False
    assert norm.procedure_requested is False
    assert norm.procedure_blocked is True


def test_normalization_short_budget_and_laptop_alias():
    norm = normalize_query_intent("예산은 6천이고 노트북 구매 예정인데 계약방법이랑 지역업체 활용방안 정리해줘")

    assert norm.amount == 60_000_000
    assert norm.item_name == "노트북"
    assert norm.contract_object == "goods"
    assert norm.contract_review_requested is True
    assert norm.local_support_requested is True


def test_normalization_composite_thousand_hundred_manwon():
    norm = normalize_query_intent("노트북 4천5백만원 구매는 1인 견적, 2인 견적, 종합쇼핑몰 중 뭐부터 봐야 해?")

    assert norm.amount == 45_000_000
    assert norm.item_name == "노트북"
    assert norm.contract_object == "goods"


def test_normalization_split_procurement_and_period_extension_tags():
    split = normalize_query_intent("공사랑 물품을 나눠 발주해도 되나?")
    extension = normalize_query_intent("공사기간이 늘어나면 간접비도 줘야 하나?")

    assert "split_procurement_review" in split.issue_tags
    assert "mixed_contract_object" in split.issue_tags
    assert "construction_period_extension" in extension.issue_tags
    assert "indirect_cost_review" in extension.issue_tags


def test_normalization_purchase_route_choice_is_not_company_lookup():
    norm = normalize_query_intent("종합쇼핑몰에서 냉난방기 사면 부산업체 고를 수 있나?")

    assert norm.item_name == "냉난방기"
    assert norm.local_support_requested is True
    assert norm.company_lookup_requested is False
    assert norm.company_lookup_blocked is False


def test_normalization_candidate_only_still_requests_company_lookup():
    norm = normalize_query_intent("CCTV 부산업체 후보만 보여줘")

    assert norm.item_name == "CCTV"
    assert norm.company_lookup_requested is True
    assert norm.company_lookup_only is True


def test_normalization_mixed_object_installation_and_maintenance():
    install = normalize_query_intent("장비 납품 설치 포함해서 발주하려면 물품이야 공사야?")
    maintenance = normalize_query_intent("서버 구매 유지보수 포함 계약은 물품이랑 용역을 같이 봐야 해?")

    assert "mixed_contract_object" in install.issue_tags
    assert "goods" in install.contract_object_candidates
    assert "construction" in install.contract_object_candidates
    assert "mixed_contract_object" in maintenance.issue_tags
    assert "goods" in maintenance.contract_object_candidates
    assert "service" in maintenance.contract_object_candidates


def test_normalization_agency_type_conflict():
    norm = normalize_query_intent(
        "국가기관이 컴퓨터 구매에서 부산 지역업체를 우대하려고 지방계약 지역제한 기준을 그대로 쓰면 안 되지?"
    )

    assert norm.buyer_type == "mixed"
    assert "agency_type_conflict" in norm.issue_tags


def test_normalization_landscape_construction_as_specific_construction_item():
    norm = normalize_query_intent("조경공사를 부산업체 중심으로 발주하려면 지역제한과 면허요건을 어떻게 설계해야 해?")

    assert norm.item_name == "조경공사"
    assert norm.contract_object == "construction"
    assert norm.local_support_requested is True
