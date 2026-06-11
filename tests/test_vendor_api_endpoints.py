import sqlite3

from fastapi.testclient import TestClient
from types import SimpleNamespace

from app import api_server


def _sample_vendor_row():
    return {
        "company_id": "vendor-1",
        "company_name": "Busan Test Vendor",
        "location": "부산광역시",
        "detail_address": "부산광역시 해운대구",
        "business_status": "active",
        "display_status": "active",
        "license_or_business_type": "software",
        "main_products": "computer",
        "candidate_types": "policy_company|shopping_mall_supplier|certified_product",
        "primary_candidate_type": "local_procurement_company",
        "policy_subtypes": "women_company",
        "certified_product_types": "innovation_product",
        "is_sme_competition_product": "true",
        "shopping_mall_flags": "mas|shopping_mall",
        "has_shopping_mall": "true",
        "has_mas": "true",
        "certified_product_summary": "computer / 123 / innovation / valid",
        "shopping_mall_product_summary": "computer / 456 / mall / valid",
        "mas_product_summary": "computer / 789 / mas / valid",
        "direct_production_summary": "computer / direct-production / valid",
        "construction_capacity_summary": "정보통신공사업 / 1200000000",
        "venture_nara_product_summary": "computer / IT / 2026-12-31",
        "venture_nara_order_summary": "computer / 3 / 15000000 / 2026-05-01",
        "direct_production_flags": "direct_production_registered",
        "procurement_attributes": "sme_competition_product",
        "general_certifications": "ISO9001",
        "manufacturer_type": "manufacturer",
        "business_status_freshness": "fresh",
        "source_refreshed_at": "2026-05-19",
    }


def test_vendor_search_json_endpoint(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_vendor_search_rows",
        lambda q, region="부산", limit=50: [{**_sample_vendor_row(), "matched_source": "product"}],
    )
    client = TestClient(api_server.app)

    response = client.get("/vendors/search?q=computer&region=busan&limit=10")

    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    assert body["rows"][0]["company_name"] == "Busan Test Vendor"
    assert body["rows"][0]["has_mas"] == "true"
    assert "direct_production_summary" in body["columns"]


def test_vendor_query_csv_endpoint(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_vendor_search_rows",
        lambda q, region="부산", limit=50: [{**_sample_vendor_row(), "matched_source": "product"}],
    )
    client = TestClient(api_server.app)

    response = client.get("/vendors/query.csv?q=computer&region=busan&limit=10")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert b"Busan Test Vendor" in response.content
    assert b"matched_source" in response.content
    assert b"direct_production_summary" in response.content


def test_vendor_download_zip_endpoint(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_vendor_download_rows",
        lambda active_only=True, limit=0: [_sample_vendor_row()],
    )
    client = TestClient(api_server.app)

    response = client.get("/vendors/download.zip")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert response.content[:2] == b"PK"


def test_vendor_download_rows_active_only_keeps_unknown_candidates(monkeypatch):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE chatbot_company_candidate_view (
            company_id TEXT,
            company_name TEXT,
            location TEXT,
            business_status TEXT,
            display_status TEXT,
            license_or_business_type TEXT,
            main_products TEXT,
            candidate_types TEXT,
            primary_candidate_type TEXT
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO chatbot_company_candidate_view (
            company_id, company_name, location, business_status, display_status,
            license_or_business_type, main_products, candidate_types, primary_candidate_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("unknown-1", "Unknown Candidate", "부산광역시", "unknown", "후보", "", "LED", "", ""),
            ("active-1", "Active Candidate", "부산광역시", "active", "active", "", "CCTV", "", ""),
            ("closed-1", "Closed Candidate", "부산광역시", "closed", "closed", "", "서적", "", ""),
        ],
    )
    conn.commit()

    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: SimpleNamespace(_connect=lambda: conn))

    rows = api_server._vendor_download_rows(active_only=True, limit=0)

    names = {row["company_name"] for row in rows}
    assert "Unknown Candidate" in names
    assert "Active Candidate" in names
    assert "Closed Candidate" not in names


def test_vendor_recommendation_search_endpoint(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_vendor_search_rows",
        lambda q, region="부산", limit=100: [{**_sample_vendor_row(), "matched_source": "product"}],
    )
    monkeypatch.setattr(
        api_server,
        "_vendor_product_policy_checks",
        lambda q, limit=5: [{
            "detail_product_code": "123",
            "detail_product_name": "computer",
            "is_sme_competition_product": "true",
            "direct_production_valid_supplier_count": "2",
        }],
    )
    client = TestClient(api_server.app)

    response = client.get("/vendor-recommendations/search?q=computer&region=busan&limit=10&budget_krw=45000000&include_product_policy=true")

    assert response.status_code == 200
    body = response.json()
    assert body["llm_used"] is False
    assert body["mode"] == "vendor_recommendation_only"
    assert body["budget_krw"] == 45000000
    assert body["budget_label"] == "4,500만원"
    assert body["rows"][0]["company_name"] == "Busan Test Vendor"
    assert "직접생산증명서 확인" in body["rows"][0]["contract_review_types"]
    assert body["rows"][0]["direct_production_certificate_status"] == "직접생산증명서 정보 있음"
    assert body["rows"][0]["direct_production_certificate_products"] == "computer / direct-production / valid"
    assert body["rows"][0]["shopping_mall_product_summary"] == "computer / 456 / mall / valid"
    assert body["rows"][0]["mas_product_summary"] == "computer / 789 / mas / valid"
    assert body["rows"][0]["construction_capacity_summary"] == "정보통신공사업 / 1200000000"
    assert body["rows"][0]["venture_nara_product_summary"] == "computer / IT / 2026-12-31"
    assert body["rows"][0]["venture_nara_order_summary"] == "computer / 3 / 15000000 / 2026-05-01"
    assert body["rows"][0]["construction_capacity_status_label"] == "시공능력평가금액 정보 있음"
    assert body["rows"][0]["venture_nara_status_label"] == "벤처나라 정보 있음"
    assert body["rows"][0]["business_status_label"] == "정상 영업"
    assert body["rows"][0]["business_status_freshness_label"] == "최신 검증"
    assert body["rows"][0]["policy_company_labels"] == "여성기업"
    assert body["rows"][0]["certified_product_labels"] == "혁신제품"
    assert body["rows"][0]["sme_competition_product_label"] == "해당 가능"
    assert "예산 4,500만원 입력됨" in body["rows"][0]["budget_review_hint"]
    assert "계약방법 확정은 계약검토 서비스로 분리" in body["rows"][0]["budget_review_hint"]
    assert "MAS/쇼핑몰 계약상태" in body["rows"][0]["recommended_checks"]
    assert "시공능력평가금액" in body["rows"][0]["recommended_checks"]
    assert "벤처나라" in body["rows"][0]["recommended_checks"]
    assert body["item_policy_summary"]["sme_competition_product"] == "해당 가능"
    assert "직접생산증명서" in body["item_policy_summary"]["direct_production_certificate"]
    assert "조합추천" in body["item_policy_summary"]["cooperative_purchase_route"]
    assert body["product_policy_checks"][0]["detail_product_code"] == "123"


def test_vendor_query_plan_adds_construction_license_terms():
    cases = [
        ("금속창호공사 업체 추천", "금속창호공사업"),
        ("금속창호공사 업체 추천", "금속창호ㆍ지붕건축물조립공사업"),
        ("상하수도설비공사 부산업체", "상하수도설비공사업"),
        ("실내건축공사 가능한 업체", "실내건축공사업"),
        ("전기공사 가능한 부산업체", "전기공사업"),
        ("정보통신공사 면허 업체", "정보통신공사업"),
        ("소방시설공사 시공능력 업체", "전문소방시설공사업"),
        ("기계설비공사 지역업체", "기계설비공사업"),
        ("방수공사 가능한 업체", "도장ㆍ습식ㆍ방수ㆍ석공사업"),
    ]
    for query, expected in cases:
        plan = api_server._vendor_query_plan(query)
        assert any(item["search_type"] == "license" and item["term"] == expected for item in plan)


def test_vendor_query_plan_adds_service_license_terms():
    cases = [
        ("건축설계 용역 업체 추천", "건축사사무소"),
        ("토목 실시설계 기술용역 업체", "엔지니어링사업자"),
        ("공공측량 용역 가능한 업체", "공공측량업"),
        ("폐기물 수집 운반 용역 업체", "폐기물수집운반업"),
        ("소독방역 용역 업체", "소독업"),
        ("청사 청소용역 업체", "건물위생관리업"),
        ("정보시스템 유지보수 업체", "소프트웨어사업자(컴퓨터관련서비스사업)"),
    ]
    for query, expected in cases:
        plan = api_server._vendor_query_plan(query)
        assert any(item["search_type"] == "license" and item["term"] == expected for item in plan)


def test_vendor_apply_construction_evidence_prioritizes_capacity_match():
    rows = [
        {
            "company_id": "a",
            "company_name": "Capacity Vendor",
            "license_or_business_type": "실내건축공사업",
            "construction_capacity_summary": "실내건축공사업^^1534663000^^busan_hq_license_snapshot_file",
            "review_score": 50,
        },
        {
            "company_id": "b",
            "company_name": "License Only Vendor",
            "license_or_business_type": "실내건축공사업",
            "construction_capacity_summary": "",
            "review_score": 50,
        },
    ]

    updated = api_server._vendor_apply_construction_evidence(rows, "실내건축공사 업체 추천")

    assert updated[0]["company_name"] == "Capacity Vendor"
    assert updated[0]["construction_capacity_amount"] == 1534663000
    assert "시공능력 확인" in updated[0]["construction_capacity_match"]
    assert "요청 면허 일치" in updated[0]["construction_license_match"]
    assert updated[1]["construction_capacity_amount"] == ""


def test_vendor_evidence_terms_include_license_for_mixed_conditions():
    terms = api_server._vendor_evidence_search_terms("복층유리와 상하수도설비공사 둘 다 가능한 업체")

    assert "복층유리" in terms
    assert "상하수도설비공사업" in terms


def test_vendor_join_formats_venture_order_summary_with_count_and_amount():
    summary = api_server._vendor_join([
        {
            "detail_product_name": "분전반",
            "order_count": "10",
            "total_amount": "44352812",
            "last_order_date": "20251117",
        }
    ])

    assert summary == "분전반 / 10건 / 44,352,812원 / 20251117"


def test_vendor_search_expands_service_question_and_filters_unrelated_rows(monkeypatch):
    event_row = {
        **_sample_vendor_row(),
        "company_id": "event-1",
        "company_name": "부산행사기획",
        "main_products": ["기타행사기획및대행서비스"],
        "license_or_business_type": [],
    }
    unrelated_row = {
        **_sample_vendor_row(),
        "company_id": "clean-1",
        "company_name": "부산청소",
        "main_products": ["건물청소서비스"],
        "license_or_business_type": [],
    }

    def search_by_product(term, limit=20):
        if term in {"행사", "기타행사기획및대행서비스"}:
            return {"candidates": [event_row, unrelated_row]}
        return {"candidates": []}

    fake_company_db = SimpleNamespace(
        search_by_product=search_by_product,
        search_by_license=lambda term, limit=20: {"candidates": []},
        search_by_company_name=lambda term, limit=20: {"candidates": []},
        search_shopping_mall_product=lambda term, limit=20: {"candidates": []},
        search_certified_product=lambda term, limit=20: {"candidates": []},
        search_innovation_product=lambda term, limit=20: {"candidates": []},
        search_excellent_procurement_product=lambda term, limit=20: {"candidates": []},
    )
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: fake_company_db)

    rows = api_server._vendor_search_rows("발대식 행사 용역 예산 2억원 업체 추천", region="busan", limit=10)

    assert [row["company_name"] for row in rows] == ["부산행사기획"]
    assert rows[0]["matched_query_label"] in {"품목: 행사", "품목: 기타행사기획및대행서비스"}


def test_vendor_search_rows_excludes_closed_or_suspended_business(monkeypatch):
    active_row = {
        **_sample_vendor_row(),
        "company_id": "active-vendor",
        "company_name": "Active Vendor",
        "business_status": "active",
    }
    closed_row = {
        **_sample_vendor_row(),
        "company_id": "closed-vendor",
        "company_name": "Closed Vendor",
        "business_status": "closed",
    }
    suspended_row = {
        **_sample_vendor_row(),
        "company_id": "suspended-vendor",
        "company_name": "Suspended Vendor",
        "business_status": "suspended",
    }
    fake_company_db = SimpleNamespace(
        search_by_product=lambda term, limit=20: {"candidates": [closed_row, suspended_row, active_row]},
        search_by_license=lambda term, limit=20: {"candidates": []},
        search_by_company_name=lambda term, limit=20: {"candidates": []},
        search_shopping_mall_product=lambda term, limit=20: {"candidates": []},
        search_certified_product=lambda term, limit=20: {"candidates": []},
        search_innovation_product=lambda term, limit=20: {"candidates": []},
        search_excellent_procurement_product=lambda term, limit=20: {"candidates": []},
    )
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: fake_company_db)

    rows = api_server._vendor_search_rows("computer", region="", limit=10)

    assert [row["company_name"] for row in rows] == ["Active Vendor"]


def test_vendor_query_plan_uses_item_normalization_policy_terms():
    electric_plan = api_server._vendor_query_plan("전기공사 부산 업체")
    electric_terms = {(item["search_type"], item["term"]) for item in electric_plan}
    assert ("product", "전기공사") in electric_terms
    assert ("license", "전기공사업") in electric_terms

    fire_plan = api_server._vendor_query_plan("소방시설공사 업체")
    fire_terms = {(item["search_type"], item["term"]) for item in fire_plan}
    assert ("product", "소방공사") in fire_terms
    assert ("license", "소방시설업") in fire_terms

    communication_plan = api_server._vendor_query_plan("정보통신 공사 업체")
    communication_terms = {(item["search_type"], item["term"]) for item in communication_plan}
    assert ("product", "정보통신공사") in communication_terms
    assert ("license", "정보통신공사업") in communication_terms


def test_vendor_query_plan_does_not_add_license_search_for_plain_product_term():
    plan = api_server._vendor_query_plan("LED")
    terms = {(item["search_type"], item["term"]) for item in plan}

    assert ("product", "LED") in terms
    assert ("license", "LED") not in terms


def test_vendor_query_plan_prioritizes_print_over_event():
    plan = api_server._vendor_query_plan("홍보물 인쇄 제작 업체")

    assert plan[0]["search_type"] == "product"
    assert plan[0]["term"] == "인쇄물"
    assert "행사" not in plan[0]["term"]


def test_vendor_query_plan_prioritizes_interpretation_over_event():
    plan = api_server._vendor_query_plan("통역 행사 지원 업체")

    assert plan[0]["search_type"] == "product"
    assert plan[0]["term"] == "통역"


def test_vendor_query_tokens_prioritize_interpretation_over_event():
    tokens = api_server._vendor_query_tokens("통역 행사 지원 업체")

    assert tokens[0] == "통역"
    assert "행사" not in tokens[:3]


def test_vendor_query_plan_expands_paving_work():
    terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan("도로포장공사 부산업체")}

    assert ("product", "도로포장공사") in terms
    assert ("license", "지반조성ㆍ포장공사업") in terms


def test_vendor_query_plan_extracts_policy_product_terms():
    remicon_terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan("직접생산 레미콘 부산업체")}
    ascon_terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan("아스콘 구매 부산업체")}

    assert ("product", "레미콘") in remicon_terms
    assert ("product", "아스콘") in ascon_terms
    assert ("product", "아스팔트콘크리트") in ascon_terms


def test_vendor_query_plan_normalizes_kitchen_and_english_remicon_terms():
    kitchen_terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan("조리기기 납품 업체")}
    english_remicon_terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan("ready mixed concrete 부산 업체")}

    assert ("product", "주방기기") in kitchen_terms
    assert ("product", "조리기기") in kitchen_terms
    assert ("product", "레미콘") in english_remicon_terms


def test_vendor_query_plan_normalizes_security_software_terms():
    plan = api_server._vendor_query_plan("백신 프로그램 납품 업체")
    terms = {(item["search_type"], item["term"]) for item in plan}

    assert plan[0]["term"] == "보안소프트웨어"
    assert ("product", "소프트웨어") in terms
    assert ("product", "보안소프트웨어") in terms
    assert ("product", "백신 프로그램 납품 업체") not in terms


def test_vendor_query_plan_expands_common_product_and_license_terms():
    cases = [
        ("도서 구매 업체", ("product", "서적")),
        ("급식 식육 납품 업체", ("product", "식육류")),
        ("건축설계용역 업체", ("license", "건축사사무소")),
        ("정보시스템 유지관리 업체", ("product", "정보시스템유지관리서비스")),
        ("구내방송장치 설치 업체", ("product", "구내방송장치")),
        ("폐기물 수집 운반 업체", ("license", "폐기물수집·운반업")),
        ("측량 용역 업체", ("license", "측량업(기타-일반측량업)")),
        ("전세버스 업체", ("product", "전세버스")),
    ]

    for query, expected in cases:
        terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan(query)}
        assert expected in terms


def test_vendor_query_plan_does_not_treat_library_context_as_book_purchase():
    plan = api_server._vendor_query_plan("도서관 담당자가 정품토너 부산 지역업체 찾아줘")
    terms = {(item["search_type"], item["term"]) for item in plan}

    assert ("product", "서적") not in terms
    assert ("product", "토너") in terms


def test_vendor_query_plan_prefers_specific_terms_over_broad_aliases():
    cases = [
        ("홍보 마케팅 용역 업체", ("product", "홍보및마케팅서비스")),
        ("홍보 마케팅 용역 업체", ("license", "광고대행업")),
        ("음향 조명 장비 임대 업체", ("product", "영상.음향및조명장치임대서비스")),
        ("손소독제 구매 업체", ("product", "손소독제")),
    ]

    for query, expected in cases:
        terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan(query)}
        assert expected in terms


def test_vendor_policy_preference_summary_reports_missing_requested_policy():
    rows = [{**_sample_vendor_row(), "policy_company_labels": "", "policy_subtypes": ""}]

    summary = api_server._vendor_policy_preference_summary("장애인기업 청소용역 업체", rows)

    assert summary["status"] == "not_found_in_candidates"
    assert summary["requested"][0]["label"] == "장애인기업"
    assert summary["matched_count"] == 0


def test_vendor_policy_preference_summary_adds_policy_db_alternatives(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_VENDOR_POLICY_COMPANY_CACHE",
        [{
            "company_name": "장애청소",
            "location": "부산광역시 동래구",
            "business_type": "중소기업",
            "industry": "건물위생관리업",
            "representative_product": "건물청소서비스",
            "manufacturer": "N",
            "registered_at": "20260101",
            "policy_labels": ["장애인기업"],
            "source": "policy_companies_json",
        }],
    )

    rows = [{**_sample_vendor_row(), "policy_company_labels": "", "policy_subtypes": ""}]
    summary = api_server._vendor_policy_preference_summary("장애인기업 청소용역 업체", rows)

    assert summary["status"] == "not_found_in_candidates"
    assert summary["alternative_count"] == 1
    assert summary["alternatives"][0]["company_name"] == "장애청소"
    assert "청소" in summary["alternatives"][0]["matched_terms"]


def test_vendor_policy_preference_summary_matches_requested_policy():
    rows = [{**_sample_vendor_row(), "policy_company_labels": "여성기업", "policy_subtypes": "women_company"}]

    summary = api_server._vendor_policy_preference_summary("여성기업 LED 업체", rows)

    assert summary["status"] == "matched"
    assert summary["matched_count"] == 1


def test_vendor_policy_preference_summary_recognizes_expanded_policy_terms():
    cases = [
        ("소상공인 LED 업체", "small_business", "소상공인"),
        ("창업기업 소프트웨어 업체", "startup", "창업기업"),
        ("청년 창업기업 디자인 업체", "youth_startup", "청년창업기업"),
        ("벤처기업 정보시스템 업체", "venture_company", "벤처기업"),
        ("사회적협동조합 행사 업체", "social_cooperative", "사회적협동조합"),
        ("자활기업 청소 업체", "self_support_company", "자활기업"),
        ("마을기업 식품 업체", "village_company", "마을기업"),
    ]

    for query, key, label in cases:
        requested = api_server._vendor_requested_policy_preferences(query)
        assert {"key": key, "label": label} in requested


def test_vendor_recommendation_rows_uses_bounded_candidate_pool(monkeypatch):
    calls = []

    def fake_search_rows(q, region="부산", limit=50):
        calls.append(limit)
        return [
            {
                **_sample_vendor_row(),
                "company_id": f"vendor-{idx}",
                "company_name": f"Vendor {idx}",
            }
            for idx in range(40)
        ]

    monkeypatch.setattr(api_server, "_vendor_search_rows", fake_search_rows)

    rows = api_server._vendor_recommendation_rows("LED", region="busan", limit=2)

    assert calls == [15]
    assert len(rows) == 2

    calls.clear()
    rows = api_server._vendor_recommendation_rows("LED", region="busan", limit=30)

    assert calls == [38]
    assert len(rows) == 30


def test_vendor_search_rows_stops_after_requested_unique_rows(monkeypatch):
    calls = []

    def search_by_product(term, limit=20):
        calls.append(("product", term, limit))
        return {
            "candidates": [
                {
                    **_sample_vendor_row(),
                    "company_id": f"vendor-{idx}",
                    "company_name": f"Vendor {idx}",
                }
                for idx in range(limit)
            ]
        }

    def fail_extra_search(*args, **kwargs):
        raise AssertionError("search should stop after requested rows are collected")

    fake_company_db = SimpleNamespace(
        search_by_product=search_by_product,
        search_by_license=fail_extra_search,
        search_by_company_name=fail_extra_search,
        search_shopping_mall_product=fail_extra_search,
        search_certified_product=fail_extra_search,
        search_innovation_product=fail_extra_search,
        search_excellent_procurement_product=fail_extra_search,
    )
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: fake_company_db)

    rows = api_server._vendor_search_rows("LED", region="", limit=5)

    assert len(rows) == 5
    assert calls == [("product", "LED", 20)]


def test_vendor_query_tokens_include_normalized_item_aliases():
    led_tokens = api_server._vendor_query_tokens("엘이디등 구매")
    assert "led" in led_tokens
    assert "led조명" in led_tokens

    cctv_tokens = api_server._vendor_query_tokens("씨씨티비 감시카메라 설치")
    assert "cctv" in cctv_tokens
    assert "영상감시장치" in cctv_tokens


def test_vendor_product_policy_checks_use_normalized_product_terms(monkeypatch):
    calls = []

    def fake_monitoring_get(endpoint, params, timeout=2.0):
        calls.append(params["keyword"])
        if params["keyword"] == "데스크톱컴퓨터":
            return {
                "candidates": [{
                    "detail_product_code": "4321150701",
                    "detail_product_name": "데스크톱컴퓨터",
                    "is_sme_competition_product": "1",
                    "direct_production_valid_supplier_count": "5",
                }]
            }
        return {"candidates": []}

    monkeypatch.setattr(api_server, "_monitoring_api_get", fake_monitoring_get)

    checks = api_server._vendor_product_policy_checks("데스크탑 컴퓨터 구매 부산업체", limit=5)

    assert checks[0]["detail_product_code"] == "4321150701"
    assert checks[0]["matched_policy_keyword"] == "데스크톱컴퓨터"
    assert "데스크탑 컴퓨터 구매 부산업체" not in calls


def test_vendor_product_policy_checks_prefer_db_adapter(monkeypatch):
    fake_company_db = SimpleNamespace(
        search_product_policy=lambda keyword, limit=5: {
            "meta": {"source": "product_policy_summary"},
            "candidates": [{
                "detail_product_code": "3911160301",
                "detail_product_name": "LED경관조명기구",
                "is_sme_competition_product": "1",
                "direct_production_valid_supplier_count": "39",
            }],
        }
    )
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: fake_company_db)

    def fail_monitoring_api(*args, **kwargs):
        raise AssertionError("monitoring API should not be called when DB policy view returns data")

    monkeypatch.setattr(api_server, "_monitoring_api_get", fail_monitoring_api)

    checks = api_server._vendor_product_policy_checks("LED 조명", limit=5)

    assert checks[0]["detail_product_code"] == "3911160301"
    assert checks[0]["matched_policy_keyword"] == "LED"
    assert checks[0]["matched_policy_source"] == "product_policy_summary"


def test_monitoring_api_fallback_uses_short_circuit_after_failure(monkeypatch):
    calls = []

    def fail_get(*args, **kwargs):
        calls.append((args, kwargs))
        raise RuntimeError("monitoring API unavailable")

    monkeypatch.setattr(api_server.requests, "get", fail_get)
    monkeypatch.setattr(api_server, "_MONITORING_API_FALLBACK_DISABLED_UNTIL", 0.0)
    monkeypatch.setenv("MONITORING_COMPANY_API_FALLBACK_COOLDOWN_SEC", "60")

    assert api_server._monitoring_api_get("/api/chatbot/product-policy/search", {"keyword": "LED"}, timeout=0.01) is None
    assert api_server._monitoring_api_get("/api/chatbot/product-policy/search", {"keyword": "CCTV"}, timeout=0.01) is None
    assert len(calls) == 1


def test_vendor_filter_keeps_strong_product_match_even_with_secondary_license_noise():
    cleaning_row = {
        **_sample_vendor_row(),
        "company_id": "cleaning-strong",
        "company_name": "부산청소",
        "main_products": "건물청소서비스",
        "license_or_business_type": "건물위생관리업|기타자유업(행사대행업)",
    }
    security_noise_row = {
        **_sample_vendor_row(),
        "company_id": "security-noise",
        "company_name": "부산경비",
        "main_products": "시설물경비서비스",
        "license_or_business_type": "청소용역|경비용역",
    }

    rows = api_server._vendor_filter_relevant_rows(
        [security_noise_row, cleaning_row],
        "건물 청소용역 부산업체",
    )

    assert [row["company_name"] for row in rows] == ["부산청소"]


def test_vendor_query_plan_keeps_medical_vaccine_out_of_security_software():
    plan = api_server._vendor_query_plan("예방접종 백신 구매 업체")
    terms = {(item["search_type"], item["term"]) for item in plan}

    assert ("product", "보안소프트웨어") not in terms
    assert ("product", "소프트웨어") not in terms


def test_vendor_search_does_not_fallback_to_unrelated_rows_for_medical_vaccine(monkeypatch):
    fake_company_db = SimpleNamespace(
        search_by_product=lambda term, limit=20: {"candidates": []},
        search_by_license=lambda term, limit=20: {"candidates": []},
        search_by_company_name=lambda term, limit=20: {"candidates": []},
        search_shopping_mall_product=lambda term, limit=20: {"candidates": []},
        search_certified_product=lambda term, limit=20: {"candidates": []},
        search_innovation_product=lambda term, limit=20: {"candidates": []},
        search_excellent_procurement_product=lambda term, limit=20: {"candidates": []},
    )
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: fake_company_db)
    monkeypatch.setattr(api_server, "_vendor_basic_search_rows", lambda *args, **kwargs: [_sample_vendor_row()])

    rows = api_server._vendor_search_rows("예방접종 백신 구매 업체", region="busan", limit=5)

    assert rows == []


def test_vendor_query_plan_prefers_disinfection_service_over_sanitizer_for_service_context():
    plan = api_server._vendor_query_plan("소독 방역 용역 업체")
    terms = {(item["search_type"], item["term"]) for item in plan}

    assert ("product", "방역서비스") in terms
    assert ("license", "소독업") in terms
    assert ("product", "손소독제") not in terms


def test_vendor_match_rank_score_prefers_exact_item_over_broad_fallback():
    exact_rental = {
        **_sample_vendor_row(),
        "company_id": "rental",
        "matched_query": "영상.음향및조명장치임대서비스",
        "matched_query_label": "품목정규화(음향조명임대): 영상.음향및조명장치임대서비스",
        "main_products": "영상.음향및조명장치임대서비스",
        "license_or_business_type": "기타자유업(행사대행업)",
    }
    broad_led = {
        **_sample_vendor_row(),
        "company_id": "led",
        "matched_query": "조명",
        "matched_query_label": "품목: 조명",
        "main_products": "LED다운라이트",
        "license_or_business_type": "전기공사업",
        "has_mas": "true",
        "has_shopping_mall": "true",
        "certified_product_types": "excellent_procurement_product",
        "policy_subtypes": "women_company",
    }

    assert api_server._vendor_match_rank_score(exact_rental, "음향 조명 장비 임대 업체") > api_server._vendor_match_rank_score(broad_led, "음향 조명 장비 임대 업체")


def test_vendor_match_rank_score_boosts_requested_policy_condition():
    startup_row = {
        **_sample_vendor_row(),
        "policy_company_labels": "창업기업",
        "policy_subtypes": "startup",
        "main_products": "소프트웨어",
    }
    normal_row = {
        **_sample_vendor_row(),
        "policy_company_labels": "",
        "policy_subtypes": "",
        "main_products": "소프트웨어",
    }

    assert api_server._vendor_match_rank_score(startup_row, "창업기업 소프트웨어 업체") > api_server._vendor_match_rank_score(normal_row, "창업기업 소프트웨어 업체")


def test_vendor_recommendation_rows_sort_by_match_rank_before_review_score(monkeypatch):
    exact_projector = {
        **_sample_vendor_row(),
        "company_id": "projector",
        "company_name": "프로젝터전문",
        "matched_query": "비디오프로젝터",
        "matched_query_label": "품목정규화(비디오프로젝터): 비디오프로젝터",
        "main_products": "비디오프로젝터",
        "has_mas": "",
        "has_shopping_mall": "",
        "certified_product_types": "",
        "policy_subtypes": "",
    }
    broad_board = {
        **_sample_vendor_row(),
        "company_id": "board",
        "company_name": "전자칠판업체",
        "matched_query": "비디오프로젝터",
        "matched_query_label": "품목정규화(비디오프로젝터): 비디오프로젝터",
        "main_products": "인터랙티브화이트보드",
        "has_mas": "true",
        "has_shopping_mall": "true",
        "certified_product_types": "innovation_product",
        "policy_subtypes": "women_company",
    }
    monkeypatch.setattr(api_server, "_vendor_search_rows", lambda q, region="부산", limit=30: [broad_board, exact_projector])

    rows = api_server._vendor_recommendation_rows("빔프로젝터 구매 업체", limit=2)

    assert rows[0]["company_name"] == "프로젝터전문"


def test_vendor_product_policy_checks_sort_specific_pc_and_toner_matches_first():
    pc_checks = [
        {"detail_product_name": "컴퓨터책상", "direct_production_valid_supplier_count": "10", "matched_policy_keyword": "컴퓨터"},
        {"detail_product_name": "데스크톱컴퓨터", "direct_production_valid_supplier_count": "1", "matched_policy_keyword": "데스크톱컴퓨터"},
    ]
    toner_checks = [
        {"detail_product_name": "프린터", "direct_production_valid_supplier_count": "10", "matched_policy_keyword": "프린터"},
        {"detail_product_name": "재제조토너", "direct_production_valid_supplier_count": "0", "matched_policy_keyword": "토너"},
    ]

    assert api_server._vendor_sort_product_policy_checks("PC 구매 업체", pc_checks)[0]["detail_product_name"] == "데스크톱컴퓨터"
    assert api_server._vendor_sort_product_policy_checks("정품토너 구매 업체", toner_checks)[0]["detail_product_name"] == "재제조토너"


def test_vendor_product_policy_checks_reorders_pc_abbreviation_before_lookup(monkeypatch):
    calls = []

    def fake_search_product_policy(keyword, limit=5):
        calls.append(keyword)
        if keyword == "PC":
            return {
                "meta": {"source": "product_policy_summary"},
                "candidates": [{
                    "detail_product_code": "3115999201",
                    "detail_product_name": "PC강선",
                    "is_sme_competition_product": "0",
                }],
            }
        if keyword == "데스크톱컴퓨터":
            return {
                "meta": {"source": "product_policy_summary"},
                "candidates": [{
                    "detail_product_code": "4321150701",
                    "detail_product_name": "데스크톱컴퓨터",
                    "is_sme_competition_product": "1",
                }],
            }
        return {"meta": {"source": "product_policy_summary"}, "candidates": []}

    monkeypatch.setattr(
        api_server,
        "_vendor_import_company_db",
        lambda: SimpleNamespace(search_product_policy=fake_search_product_policy),
    )

    checks = api_server._vendor_product_policy_checks("PC 업체 후보 중기간경쟁 해당 여부 포함해서", limit=5)

    assert calls[0] == "데스크톱컴퓨터"
    assert "PC" not in calls
    assert checks[0]["detail_product_name"] == "데스크톱컴퓨터"


def test_vendor_product_policy_check_gate_skips_service_queries():
    assert api_server._vendor_should_check_product_policy("정품토너 구매 업체") is True
    assert api_server._vendor_should_check_product_policy("데스크톱 컴퓨터 납품 업체") is True
    assert api_server._vendor_should_check_product_policy("번역용역 부산 업체") is False
    assert api_server._vendor_should_check_product_policy("청사 경비용역 부산 업체") is False
