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


def test_expanded_vendor_search_terms_normalize_for_company_lookup():
    cases = [
        ("도서 구매 업체", "도서", "서적"),
        ("급식 식육 납품 업체", "식육", "식육류"),
        ("건축설계용역 업체", "건축설계", "건축설계용역"),
        ("정보시스템 유지관리 업체", "정보시스템", "정보시스템개발서비스"),
        ("구내방송장치 설치 업체", "방송장치", "구내방송장치"),
        ("폐기물 수집 운반 업체", "폐기물", "폐기물수집·운반업"),
        ("측량 용역 업체", "측량", "측량업(기타-일반측량업)"),
        ("전세버스 업체", "여행전세버스", "국내여행업"),
    ]

    for query, canonical_name, primary_search_term in cases:
        result = normalize_item_query(query)
        assert result.found is True
        assert result.canonical_name == canonical_name
        assert result.primary_search_term == primary_search_term


def test_preferred_vendor_terms_win_over_broad_aliases():
    cases = [
        ("홍보 마케팅 용역 업체", "홍보마케팅", "홍보및마케팅서비스"),
        ("음향 조명 장비 임대 업체", "음향조명임대", "영상.음향및조명장치임대서비스"),
        ("손소독제 구매 업체", "손소독제", "손소독제"),
    ]

    for query, canonical_name, primary_search_term in cases:
        result = normalize_item_query(query)
        assert result.found is True
        assert result.reason == "preferred_alias"
        assert result.canonical_name == canonical_name
        assert result.primary_search_term == primary_search_term


def test_negative_context_does_not_route_medical_vaccine_to_security_software():
    result = normalize_item_query("예방접종 백신 구매 업체")

    assert result.found is False


def test_policy_company_context_does_not_route_to_book_by_single_syllable():
    result = normalize_item_query("정품토너 업체를 정책기업 여부까지 같이 보고 싶다")

    assert result.found is True
    assert result.canonical_name == "토너"
    assert result.primary_search_term == "정품토너"


def test_disinfection_service_does_not_route_to_hand_sanitizer():
    result = normalize_item_query("소독 방역 용역 업체")

    assert result.found is True
    assert result.canonical_name == "방역소독"
    assert result.primary_search_term == "방역서비스"


def test_pc_and_notebook_queries_prefer_detail_item_names():
    pc = normalize_item_query("PC 30대 구매 부산업체")
    notebook = normalize_item_query("랩톱 노트북 구매 업체")

    assert pc.primary_search_term == "데스크톱컴퓨터"
    assert "노트북컴퓨터" in pc.search_terms
    assert notebook.primary_search_term == "노트북"
    assert "노트북컴퓨터" in notebook.search_terms
