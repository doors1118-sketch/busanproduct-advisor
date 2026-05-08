from app.policies.procurement_router_lexicon import (
    support_catalog_keywords,
    validator_keywords,
)


def test_keyword_pre_router_uses_manual_lexicon_for_concepts():
    from app.prompting.keyword_pre_router import keyword_pre_route

    result = keyword_pre_route("추정가격 예정가격 기초금액 차이가 뭐야?")

    assert "procurement_general" in result.matched_categories
    assert not result.is_unambiguous


def test_keyword_pre_router_uses_public_purchase_terms():
    from app.prompting.keyword_pre_router import keyword_pre_route

    result = keyword_pre_route("공사용자재 직접구매 대상 품목인지 확인해줘")

    assert "policy_candidate_search" in result.matched_categories
    assert not result.is_unambiguous


def test_validator_keywords_include_public_purchase_terms():
    assert "공공구매제도" in validator_keywords("eligibility_keywords")
    assert "추정가격" in validator_keywords("legal_review_keywords")


def test_catalog_extensions_include_public_purchase_terms():
    assert "공공구매제도" in support_catalog_keywords("policy_company_direct_contract")
    assert "공사용자재 직접구매" in support_catalog_keywords("sme_competition_direct_production")


def test_regional_catalog_uses_manual_lexicon_extensions():
    from app.policies.regional_support_catalog import match_regional_support_catalog

    matches = match_regional_support_catalog(
        "LED 조명 공공구매 우선구매 제도와 부산업체 활용 방법 알려줘",
        contract_object="goods",
        agency_type="local_government",
    )
    ids = {match.scheme.id for match in matches}

    assert "policy_company_direct_contract" in ids
    assert "sme_competition_direct_production" in ids or "technology_development_priority_purchase" in ids


def test_router_uses_excellent_procurement_manual_terms():
    from app.prompting.keyword_pre_router import keyword_pre_route
    from app.policies.regional_support_catalog import match_regional_support_catalog

    result = keyword_pre_route("우수조달물품 지정과 제3자단가계약 체결 절차가 뭐야?")
    assert "certified_product_search" in result.matched_categories
    assert "mas_shopping_mall" in result.matched_categories
    assert not result.is_unambiguous

    ids = {
        match.scheme.id
        for match in match_regional_support_catalog(
            "우수조달물품 지정과 제3자단가계약 체결 절차가 뭐야?",
            contract_object="goods",
            agency_type="local_government",
        )
    }
    assert "shopping_mall_mas_regional_factor" in ids
    assert "technology_development_priority_purchase" in ids


def test_router_uses_construction_and_service_manual_terms():
    from app.prompting.keyword_pre_router import keyword_pre_route

    construction = keyword_pre_route("공사계약에서 주된 공사와 부대공사 개념 차이 알려줘")
    assert "construction_contract" in construction.matched_categories
    assert "procurement_general" in construction.matched_categories
    assert not construction.is_unambiguous

    service = keyword_pre_route("용역계약 제안요청서와 과업지시서 차이가 뭐야?")
    assert "service_contract" in service.matched_categories
    assert "procurement_general" in service.matched_categories
    assert not service.is_unambiguous
