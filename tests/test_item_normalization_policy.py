from app.policies.item_normalization_policy import (
    extract_item_keyword_with_synonyms,
    normalize_item_query,
)


def test_led_synonyms_normalize_to_led_lighting():
    cases = [
        "8천만원으로 led 조명을 사려고 한다",
        "8천만원 LED조명 구매",
        "엘이디 조명 부산업체 있어?",
        "LED등기구를 사려고 해",
    ]

    for query in cases:
        result = normalize_item_query(query)
        assert result.found is True
        assert result.canonical_name == "LED 조명"
        assert result.primary_search_term == "LED"
        assert "LED" in result.search_terms


def test_router_item_fallback_for_unknown_specific_item():
    result = normalize_item_query("8천만원으로 무대장치를 사려고 한다", router_item="무대장치")

    assert result.found is True
    assert result.canonical_name == "무대장치"
    assert result.reason == "router_item_fallback"


def test_extract_item_keyword_uses_synonym_dictionary_first():
    assert extract_item_keyword_with_synonyms("8천만원으로 엘이디조명 사려고 한다") == "LED"


def test_service_and_construction_terms_normalize_for_company_lookup():
    service = normalize_item_query("8천만원 청소 용역 맡기려고 한다")
    construction = normalize_item_query("2억원 전기 공사 부산업체 검토")

    assert service.canonical_name == "청소용역"
    assert service.primary_search_term == "청소용역"
    assert construction.canonical_name == "전기공사"
    assert construction.primary_search_term == "전기공사"
