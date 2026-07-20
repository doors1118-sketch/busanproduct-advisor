import json
import sqlite3

from fastapi.testclient import TestClient
from types import SimpleNamespace

from app import api_server, company_db


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
    assert body["total_candidate_count"] == 1
    assert body["visible_candidate_count"] == 1
    assert body["candidate_composition"]["basis_label"] == "전체 후보 기준"
    assert body["candidate_composition"]["total_registered_candidates"] == 1
    assert body["candidate_composition"]["direct_production_count"] == 1
    assert body["candidate_composition"]["shopping_mall_mas_count"] == 1
    assert body["candidate_composition"]["policy_company_count"] == 1
    assert body["candidate_composition"]["women_company_count"] == 1
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
    assert body["rows"][0]["sme_competition_product_label"] == "해당"
    assert "예산 4,500만원 입력됨" in body["rows"][0]["budget_review_hint"]
    assert "계약방법 확정은 계약검토 서비스로 분리" in body["rows"][0]["budget_review_hint"]
    assert "MAS/쇼핑몰 계약상태" in body["rows"][0]["recommended_checks"]
    assert "시공능력평가금액" in body["rows"][0]["recommended_checks"]
    assert "벤처나라" in body["rows"][0]["recommended_checks"]
    assert body["item_policy_summary"]["sme_competition_product"] == "해당"
    assert "직접생산증명서" in body["item_policy_summary"]["direct_production_certificate"]
    assert "조합추천" in body["item_policy_summary"]["cooperative_purchase_route"]
    assert body["product_policy_checks"][0]["detail_product_code"] == "123"
    assert body["purchase_route_guidance"]["primary_route"]["route_id"] == "two_quote_small_value"
    assert body["purchase_route_guidance"]["purchase_route_basis_level"] == "no_central_procurement_evidence"
    mas_card = next(card for card in body["purchase_route_guidance"]["route_cards"] if card["route_id"] == "shopping_mall_mas")
    assert mas_card["route_priority"] == "reference"
    assert "조달청 단가계약 근거 미확인" in mas_card["practical_note"]
    assert body["purchase_route_guidance"]["required_checks"]
    assert "purchase_route_fit_summary" in body["rows"][0]


def test_vendor_item_policy_summary_marks_explicit_non_sme_as_not_applicable():
    checks = [{
        "detail_product_code": "4319150401",
        "detail_product_name": "유선전화기",
        "matched_policy_source": "product_policy_summary_fast",
        "is_sme_competition_product": "0",
        "direct_production_valid_supplier_count": "0",
        "busan_company_product_count": "1",
    }]

    summary = api_server._vendor_item_policy_summary("유선전화기", checks, requested=True)

    assert summary["status"] == "matched"
    assert summary["sme_competition_product"] == "미해당"
    assert "중소기업자간 경쟁제품에 미해당입니다(DB 기준)" in summary["message"]
    assert summary["direct_production_certificate"] == "DB 기준 직접생산 의무 미확인"


def test_vendor_purchase_route_guidance_uses_direct_or_bid_when_only_company_product_count_exists():
    rows = [{**_sample_vendor_row(), "has_mas": "", "has_shopping_mall": ""}]
    checks = [{
        "detail_product_code": "4319150401",
        "detail_product_name": "유선전화기",
        "matched_policy_source": "product_policy_summary_fast",
        "is_sme_competition_product": "0",
        "direct_production_valid_supplier_count": "0",
        "busan_company_product_count": "1",
        "shopping_mall_active_registered_count": "0",
        "shopping_mall_active_busan_supplier_count": "0",
    }]
    summary = api_server._vendor_item_policy_summary("유선전화기", checks, requested=True)

    guidance = api_server._vendor_purchase_route_guidance("유선전화기", rows, checks, summary)

    assert guidance["primary_route"]["route_id"] == "open_market_or_bid"
    assert guidance["primary_route"]["label"] == "직접계약/입찰공고 검토"
    assert all(badge["label"] != "구매방식 확인 필요" for badge in guidance["badges"])


def test_vendor_search_rows_collects_multiple_terms_for_mixed_query(monkeypatch):
    calls = []

    def search_by_product(term, limit=20):
        calls.append(term)
        if term == "CCTV":
            return {"candidates": [{**_sample_vendor_row(), "company_id": "cctv", "company_name": "CCTV Vendor", "main_products": "CCTV"}]}
        if term in {"노트북", "컴퓨터"}:
            return {"candidates": [{**_sample_vendor_row(), "company_id": "notebook", "company_name": "Notebook Vendor", "main_products": "노트북컴퓨터"}]}
        return {"candidates": []}

    fake_company_db = SimpleNamespace(
        search_by_product=search_by_product,
        search_by_license=lambda term, limit=20: {"candidates": []},
        search_by_company_name=lambda term, limit=20: {"candidates": []},
        search_shopping_mall_product=lambda term, limit=20: {"candidates": []},
        search_certified_product=lambda term, limit=20: {"candidates": []},
        search_innovation_product=lambda term, limit=20: {"candidates": []},
        search_excellent_procurement_product=lambda term, limit=20: {"candidates": []},
        search_by_direct_production=lambda term, limit=20: {"candidates": []},
    )
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: fake_company_db)

    rows = api_server._vendor_search_rows("CCTV와 노트북 둘 다 가능한 업체", region="", limit=10)

    names = {row["company_name"] for row in rows}
    assert "CCTV Vendor" in names
    assert "Notebook Vendor" in names
    assert any(term in calls for term in {"노트북", "컴퓨터"})


def test_vendor_purchase_route_guidance_prioritizes_direct_and_mas_requirements():
    rows = [
        api_server._vendor_recommendation_row({
            **_sample_vendor_row(),
            "direct_production_summary": "데스크톱컴퓨터 / 직접생산 / valid",
            "mas_product_summary": "데스크톱컴퓨터 / MAS / active",
            "has_mas": "true",
        })
    ]
    checks = [{
        "detail_product_code": "4321150701",
        "detail_product_name": "데스크톱컴퓨터",
        "is_sme_competition_product": "1",
        "direct_production_valid_supplier_count": "5",
        "mas_active_supplier_count": "2",
        "busan_company_product_count": "3",
    }]

    guidance = api_server._vendor_purchase_route_guidance("데스크톱 컴퓨터 구매", rows, checks, {"status": "matched"})

    route_ids = {card["route_id"] for card in guidance["route_cards"]}
    badge_labels = {badge["label"] for badge in guidance["badges"]}
    assert "sme_direct_production" in route_ids
    assert "mas" in route_ids
    assert "중소기업자간 경쟁제품 해당(DB 기준)" in badge_labels
    assert "직접생산 확인 필요 품목" in badge_labels


def test_vendor_purchase_route_guidance_does_not_promote_desktop_mas_without_contract_type():
    rows = [
        api_server._vendor_recommendation_row({
            **_sample_vendor_row(),
            "direct_production_summary": "데스크톱컴퓨터 / 직접생산 / valid",
            "mas_product_summary": "데스크톱컴퓨터 / MAS / active",
            "shopping_mall_product_summary": "데스크톱컴퓨터 / 쇼핑몰 / active",
            "has_mas": "true",
            "has_shopping_mall": "true",
        })
    ]
    checks = [{
        "detail_product_code": "4321150701",
        "detail_product_name": "데스크톱컴퓨터",
        "is_sme_competition_product": "1",
        "direct_production_valid_supplier_count": "5",
    }]

    guidance = api_server._vendor_purchase_route_guidance(
        "데스크탑",
        rows,
        checks,
        {"status": "matched"},
        budget_krw=60_000_000,
    )

    assert guidance["primary_route"]["route_id"] == "two_quote_small_value"
    mas_card = next(card for card in guidance["route_cards"] if card["route_id"] == "shopping_mall_mas")
    assert mas_card["route_priority"] == "reference"
    assert mas_card["basis_level"] == "no_central_procurement_evidence"
    assert "조달청 단가계약 근거 미확인" in mas_card["practical_note"]


def test_vendor_purchase_route_guidance_promotes_confirmed_third_party_unit_price():
    rows = [
        api_server._vendor_recommendation_row({
            **_sample_vendor_row(),
            "shopping_mall_product_summary": "전자복사기 / 제3자단가계약 / active",
            "shopping_mall_flags": "third_party_unit_price_registered",
            "has_shopping_mall": "true",
        })
    ]

    guidance = api_server._vendor_purchase_route_guidance(
        "전자복사기",
        rows,
        [],
        {"status": "matched"},
        budget_krw=30_000_000,
    )

    assert guidance["primary_route"]["route_id"] == "third_party_unit_price"
    assert "제3자단가계약" in guidance["primary_route"]["label"]
    assert "계약유형=제3자단가계약" in guidance["primary_route"]["required_checks"]


def test_vendor_purchase_route_guidance_uses_item_master_third_party_signal_without_supplier_rows():
    checks = [{
        "detail_product_code": "4321150701",
        "detail_product_name": "desktop computer",
        "matched_policy_source": "pps_shopping_mall_item_policy_summary",
        "shopping_mall_active_registered_count": "12",
        "shopping_mall_active_third_party_count": "7",
        "shopping_mall_active_mas_count": "0",
        "shopping_mall_active_busan_supplier_count": "0",
    }]

    guidance = api_server._vendor_purchase_route_guidance(
        "desktop computer",
        [],
        checks,
        {"status": "matched"},
        budget_krw=30_000_000,
    )

    assert guidance["primary_route"]["route_id"] == "third_party_unit_price"
    assert guidance["primary_route"]["route_priority"] == "primary"


def test_vendor_logs_item_policy_miss_queue_when_master_evidence_is_absent(monkeypatch, tmp_path):
    queue_path = tmp_path / "vendor_item_policy_miss_queue.jsonl"
    monkeypatch.setenv("VENDOR_ITEM_POLICY_MISS_QUEUE_PATH", str(queue_path))
    monkeypatch.setenv("VENDOR_ITEM_POLICY_MISS_QUEUE_ENABLED", "true")

    api_server._vendor_log_item_policy_miss(
        "비디오프로젝터",
        [{
            "detail_product_code": "4511161601",
            "detail_product_name": "슬라이드프로젝터",
            "matched_policy_source": "product_policy_summary",
            "matched_policy_keyword": "비디오프로젝터",
        }],
        requested=True,
    )

    records = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines()]
    assert records[0]["query"] == "비디오프로젝터"
    assert records[0]["reason"] == "shopping_mall_item_master_not_matched"
    assert records[0]["review_status"] == "pending"


def test_vendor_purchase_route_guidance_prioritizes_construction_intent_over_mas_rows():
    rows = [
        api_server._vendor_recommendation_row({
            **_sample_vendor_row(),
            "license_or_business_type": "지반조성ㆍ포장공사업",
            "construction_capacity_summary": "지반조성ㆍ포장공사업 / 1200000000",
            "mas_product_summary": "아스팔트콘크리트 / MAS / active",
            "has_mas": "true",
        })
    ]

    guidance = api_server._vendor_purchase_route_guidance("도로 포장공사 면허 업체 추천", rows, [], {"status": "matched"})

    assert guidance["primary_route"]["route_id"] == "construction_license"
    assert guidance["title"] == "공사 면허/시공능력 검토"
    assert any(badge["label"] == "공사 면허/시공능력 검토" for badge in guidance["badges"])
    badge_labels = [badge["label"] for badge in guidance["badges"]]
    assert not any("MAS" in label for label in badge_labels)
    assert not any("\ub098\ub77c\uc7a5\ud130" in label for label in badge_labels)


def test_vendor_purchase_route_guidance_keeps_material_purchase_on_mas_route():
    rows = [
        api_server._vendor_recommendation_row({
            **_sample_vendor_row(),
            "license_or_business_type": "지반조성ㆍ포장공사업",
            "construction_capacity_summary": "지반조성ㆍ포장공사업 / 1200000000",
            "mas_product_summary": "아스팔트콘크리트 / MAS / active",
            "has_mas": "true",
        })
    ]

    guidance = api_server._vendor_purchase_route_guidance("도로포장 자재 구매 부산업체", rows, [], {"status": "matched"})

    assert guidance["primary_route"]["route_id"] == "mas"
    assert guidance["primary_route"]["status"] == "candidate_evidence_only"
    assert guidance["title"] == "다수공급자계약(MAS)"


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
        ("소방 안전 점검 업체", "소방시설관리업"),
        ("소방안전점검 업체", "소방시설관리업"),
        ("소방 안전 관리 대행 업체", "소방안전관리대행"),
        ("소방안전관리대행 업체", "소방안전관리대행"),
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
    assert updated[0]["condition_match_type"] == "공사면허 확인"
    assert "시공능력 근거 확인" in updated[0]["condition_match_summary"]
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
    work_terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan("도로포장공사 부산업체")}
    material_terms = {(item["search_type"], item["term"]) for item in api_server._vendor_query_plan("도로포장 자재 구매 부산업체")}

    assert ("license", "지반조성ㆍ포장공사업") in work_terms
    assert ("product", "아스팔트콘크리트") not in work_terms
    assert ("product", "아스팔트콘크리트") in material_terms
    assert ("license", "지반조성ㆍ포장공사업") in material_terms


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


def test_vendor_evidence_search_terms_prefer_policy_codes_before_broad_terms():
    terms = api_server._vendor_evidence_search_terms(
        "비디오프로젝터 구매 업체",
        [{
            "detail_product_code": "4511161601",
            "detail_product_name": "비디오프로젝터",
            "matched_policy_keyword": "프로젝터",
            "shopping_mall_product_class_code": "45111616",
        }],
    )

    assert terms[:2] == ["4511161601", "45111616"]
    assert terms.index("4511161601") < terms.index("비디오프로젝터")


def test_company_item_evidence_where_uses_code_columns_for_code_terms():
    where_sql, params = company_db._company_item_evidence_where(
        ["d.detail_product_name", "d.detail_product_code"],
        ["4511161601", "비디오프로젝터"],
    )

    assert "IFNULL(d.detail_product_code, '') = ?" in where_sql
    assert "IFNULL(d.detail_product_name, '') = ?" not in where_sql
    assert "4511161601" in params
    assert "%4511161601%" not in params
    assert "%비디오프로젝터%" in params


def test_company_db_product_aliases_include_stainless_band_variants():
    terms = company_db._terms("스텐레스밴드", "product")

    assert "스텐밴드" in terms
    assert "스테인리스밴드" in terms


def test_company_db_item_selection_options_use_alias_and_mall_summary(tmp_path, monkeypatch):
    db_path = tmp_path / "chatbot_company.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE procurement_product_alias (
            alias TEXT,
            alias_normalized TEXT,
            canonical_name TEXT,
            dtil_prdct_clsfc_no TEXT,
            prdct_clsfc_no TEXT,
            domain TEXT,
            priority INTEGER,
            is_active INTEGER
        );
        CREATE TABLE pps_shopping_mall_item_policy_summary_fast (
            detail_product_code TEXT,
            detail_product_name TEXT,
            product_class_code TEXT,
            product_class_name TEXT,
            active_registered_count INTEGER,
            active_third_party_count INTEGER,
            active_mas_count INTEGER,
            active_general_unit_price_count INTEGER,
            active_supplier_count INTEGER,
            active_busan_supplier_count INTEGER,
            active_contract_types TEXT,
            source_refreshed_at TEXT
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO procurement_product_alias
        (alias, alias_normalized, canonical_name, dtil_prdct_clsfc_no, prdct_clsfc_no, domain, priority, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """,
        [
            ("컴퓨터", "컴퓨터", "데스크톱컴퓨터", "4321150701", "43211507", "computer_equipment", 100),
            ("컴퓨터", "컴퓨터", "노트북컴퓨터", "4321150301", "43211503", "computer_equipment", 99),
        ],
    )
    conn.executemany(
        """
        INSERT INTO pps_shopping_mall_item_policy_summary_fast
        (detail_product_code, detail_product_name, product_class_code, product_class_name,
         active_registered_count, active_third_party_count, active_mas_count, active_general_unit_price_count,
         active_supplier_count, active_busan_supplier_count, active_contract_types, source_refreshed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, '2026-07-19')
        """,
        [
            ("4321150701", "데스크톱컴퓨터", "43211507", "데스크톱컴퓨터", 1723, 1344, 379, 23, 0, "mas,third_party_unit_price"),
            ("4321150301", "노트북컴퓨터", "43211503", "노트북컴퓨터", 142, 94, 48, 8, 0, "mas,third_party_unit_price"),
        ],
    )
    conn.commit()
    conn.close()
    monkeypatch.setenv("CHATBOT_COMPANY_DB_PATH", str(db_path))

    result = company_db.search_item_selection_options("컴퓨터", limit=10)

    assert result is not None
    assert result["status"] == "needs_item_selection"
    assert [item["detail_product_name"] for item in result["selection_options"]] == ["데스크톱컴퓨터", "노트북컴퓨터"]
    assert result["selection_options"][0]["active_registered_count"] == 1723


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


def test_vendor_product_policy_checks_short_circuit_after_first_single_item_match(monkeypatch):
    calls = []

    def fake_search_product_policy(keyword, limit=5):
        calls.append(keyword)
        return {
            "meta": {"source": "product_policy_summary"},
            "candidates": [{
                "detail_product_code": "4617161001",
                "detail_product_name": "영상감시장치",
                "is_sme_competition_product": "1",
            }],
        }

    fake_company_db = SimpleNamespace(
        search_facility_material_policy=lambda keyword, limit=5: {"candidates": []},
        search_shopping_mall_item_policy=lambda keyword, limit=5: {
            "candidates": [{
                "detail_product_code": "4617161001",
                "detail_product_name": "영상감시장치",
                "active_busan_supplier_count": "2",
            }]
        },
        search_product_policy=fake_search_product_policy,
    )
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: fake_company_db)

    checks = api_server._vendor_product_policy_checks("CCTV 구매 업체", limit=5)

    assert checks[0]["detail_product_name"] == "영상감시장치"
    assert calls == ["CCTV"]


def test_vendor_product_policy_checks_continue_fast_mall_aliases_without_repeating_slow_policy(monkeypatch):
    policy_calls = []
    mall_calls = []

    def fake_search_product_policy(keyword, limit=5):
        policy_calls.append(keyword)
        return {
            "meta": {"source": "product_policy_summary"},
            "candidates": [{
                "detail_product_code": "4617161001",
                "detail_product_name": "영상감시장치",
                "is_sme_competition_product": "1",
            }],
        }

    def fake_search_shopping_mall_item_policy(keyword, limit=5):
        mall_calls.append(keyword)
        busan_count = "3" if keyword == "보안캠" else "0"
        return {
            "candidates": [{
                "detail_product_code": "4617161001",
                "detail_product_name": "영상감시장치",
                "active_busan_supplier_count": busan_count,
            }]
        }

    fake_company_db = SimpleNamespace(
        search_facility_material_policy=lambda keyword, limit=5: {"candidates": []},
        search_shopping_mall_item_policy=fake_search_shopping_mall_item_policy,
        search_product_policy=fake_search_product_policy,
    )
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: fake_company_db)

    checks = api_server._vendor_product_policy_checks("CCTV 구매 업체", limit=5)

    assert policy_calls == ["CCTV"]
    assert "보안캠" in mall_calls
    assert any(item.get("shopping_mall_active_busan_supplier_count") == "3" for item in checks)


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


def test_vendor_generic_telephone_requires_detail_item_selection():
    assert api_server._vendor_item_disambiguation("전화기 구매") is not None
    assert api_server._vendor_item_disambiguation("유선 전화기 구매") is None
    assert api_server._vendor_item_disambiguation("휴대전화기 구매") is None


def test_vendor_product_policy_checks_expand_generic_telephone_candidates(monkeypatch):
    calls = []
    products = {
        "유선전화기": ("4319150901", "유선전화기"),
        "일반전화기": ("4319150902", "일반전화기"),
        "휴대전화기": ("4319150101", "휴대전화기"),
        "IP전화기": ("4319151101", "IP전화기"),
        "인터넷전화기": ("4319151102", "인터넷전화기"),
    }

    def fake_search_product_policy(keyword, limit=5):
        calls.append(keyword)
        if keyword not in products:
            return {"meta": {"source": "product_policy_summary"}, "candidates": []}
        code, name = products[keyword]
        return {
            "meta": {"source": "product_policy_summary"},
            "candidates": [{
                "detail_product_code": code,
                "detail_product_name": name,
                "is_sme_competition_product": "0",
            }],
        }

    monkeypatch.setattr(
        api_server,
        "_vendor_import_company_db",
        lambda: SimpleNamespace(
            search_facility_material_policy=lambda keyword, limit=5: {"candidates": []},
            search_shopping_mall_item_policy=lambda keyword, limit=5: {"candidates": []},
            search_product_policy=fake_search_product_policy,
        ),
    )

    checks = api_server._vendor_product_policy_checks("전화기 구매", limit=5)

    assert calls[:5] == ["유선전화기", "일반전화기", "휴대전화기", "IP전화기", "인터넷전화기"]
    assert {item["detail_product_name"] for item in checks} == set(products)


def test_vendor_item_policy_summary_holds_policy_judgment_for_generic_telephone():
    checks = [
        {
            "detail_product_code": "4319150901",
            "detail_product_name": "유선전화기",
            "matched_policy_source": "product_policy_summary",
            "is_sme_competition_product": "0",
        },
        {
            "detail_product_code": "4319150101",
            "detail_product_name": "휴대전화기",
            "matched_policy_source": "product_policy_summary",
            "is_sme_competition_product": "1",
        },
        {
            "detail_product_code": "34101143",
            "detail_product_name": "구내단자함",
            "matched_policy_source": "facility_material_price_file",
            "is_sme_competition_product": "",
        },
    ]

    summary = api_server._vendor_item_policy_summary("전화기 구매", checks, requested=True)

    assert summary["status"] == "needs_item_selection"
    assert summary["selection_required"] is True
    assert summary["sme_competition_product"] == "세부품명 선택 후 판정"
    assert [item["detail_product_name"] for item in summary["selection_options"]] == ["유선전화기", "휴대전화기"]


def test_vendor_purchase_route_waits_for_detail_item_selection():
    summary = {
        "status": "needs_item_selection",
        "message": "전화기 종류를 선택해야 합니다.",
    }

    guidance = api_server._vendor_purchase_route_guidance(
        "전화기 구매",
        [],
        [{"detail_product_name": "휴대전화기", "is_sme_competition_product": "1"}],
        summary,
    )

    assert guidance["primary_route"]["route_id"] == "item_selection_required"
    assert guidance["item_policy_status"] == "needs_item_selection"
    assert guidance["badges"][0]["label"] == "세부 유형/품목 선택 필요"


def test_vendor_generic_fire_query_requires_domain_selection():
    summary = api_server._vendor_item_policy_summary("소방", [], requested=True)

    assert summary["status"] == "needs_item_selection"
    assert summary["selection_title"] == "소방 세부 유형 선택 필요"
    assert [item["detail_product_name"] for item in summary["selection_options"]] == [
        "소방시설공사",
        "소방시설점검",
        "소방안전관리대행",
        "소방용품",
    ]


def test_vendor_payload_blocks_generic_fire_candidates(monkeypatch):
    calls = []

    def fake_rows(q, region="부산", limit=100, budget_krw=None):
        calls.append(q)
        return [{**_sample_vendor_row(), "matched_source": "product"}]

    monkeypatch.setattr(api_server, "_vendor_recommendation_rows", fake_rows)
    monkeypatch.setattr(
        api_server,
        "_vendor_product_policy_checks",
        lambda q, limit=5: [{"detail_product_name": "소방선", "matched_policy_source": "product_policy_summary"}],
    )

    payload = api_server._vendor_recommendation_payload("소방", limit=10)

    assert calls == []
    assert payload["count"] == 0
    assert payload["rows"] == []
    assert payload["item_policy_summary"]["status"] == "needs_item_selection"
    assert payload["item_policy_summary"]["selection_title"] == "소방 세부 유형 선택 필요"
    assert payload["zero_result_status"]["status"] == "item_selection_required"
    assert payload["purchase_route_guidance"]["primary_route"]["label"] == "소방 세부 유형 선택 필요"


def test_vendor_payload_blocks_generic_telephone_candidates(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_vendor_recommendation_rows",
        lambda q, region="부산", limit=100, budget_krw=None: [
            {**_sample_vendor_row(), "matched_source": "product"}
        ],
    )
    monkeypatch.setattr(
        api_server,
        "_vendor_product_policy_checks",
        lambda q, limit=5: [
            {
                "detail_product_code": "4319150101",
                "detail_product_name": "휴대전화기",
                "matched_policy_source": "product_policy_summary",
                "is_sme_competition_product": "1",
            }
        ],
    )

    payload = api_server._vendor_recommendation_payload("전화기 구매", limit=10)

    assert payload["count"] == 0
    assert payload["rows"] == []
    assert payload["item_policy_summary"]["status"] == "needs_item_selection"
    assert [item["detail_product_name"] for item in payload["item_policy_summary"]["selection_options"]] == ["휴대전화기"]
    assert payload["zero_result_status"]["status"] == "item_selection_required"
    assert payload["purchase_route_guidance"]["primary_route"]["route_id"] == "item_selection_required"


def test_vendor_generic_camera_requires_detail_item_selection():
    assert api_server._vendor_item_disambiguation("카메라 구매") is not None
    assert api_server._vendor_item_disambiguation("보안카메라 구매") is None
    assert api_server._vendor_item_disambiguation("CCTV 구매") is None
    assert api_server._vendor_item_disambiguation("디지털카메라 구매") is None
    assert api_server._vendor_item_disambiguation("비디오카메라 구매") is None
    assert api_server._vendor_item_disambiguation("디카 구매") is None


def test_vendor_contract_history_terms_keep_precise_camera_queries_narrow():
    digital_terms = api_server._vendor_contract_history_terms("디지털카메라 구매")
    cctv_terms = api_server._vendor_contract_history_terms("CCTV 구매")

    assert "디지털카메라" in digital_terms
    assert "cctv" not in digital_terms
    assert "보안용카메라" not in digital_terms
    assert api_server._vendor_contract_history_min_hits(digital_terms) == 1
    assert "cctv" in cctv_terms
    assert "보안용카메라" in cctv_terms
    assert api_server._vendor_contract_history_min_hits(cctv_terms) == 2


def test_vendor_item_policy_summary_filters_generic_camera_accessories():
    checks = [
        {
            "detail_product_code": "4512152001",
            "detail_product_name": "디지털카메라",
            "matched_policy_source": "product_policy_summary",
            "is_sme_competition_product": "0",
        },
        {
            "detail_product_code": "4512151601",
            "detail_product_name": "캠코더",
            "matched_policy_source": "product_policy_summary",
            "is_sme_competition_product": "0",
        },
        {
            "detail_product_code": "4617162201",
            "detail_product_name": "영상감시장치",
            "matched_policy_source": "product_policy_summary",
            "is_sme_competition_product": "1",
        },
        {
            "detail_product_code": "4512159901",
            "detail_product_name": "카메라회전대",
            "matched_policy_source": "product_policy_summary",
            "is_sme_competition_product": "0",
        },
        {
            "detail_product_code": "4512160301",
            "detail_product_name": "카메라용렌즈",
            "matched_policy_source": "product_policy_summary",
            "is_sme_competition_product": "0",
        },
    ]

    summary = api_server._vendor_item_policy_summary("카메라 구매", checks, requested=True)

    assert summary["status"] == "needs_item_selection"
    assert summary["selection_title"] == "카메라 종류 선택 필요"
    assert [item["detail_product_name"] for item in summary["selection_options"]] == [
        "디지털카메라",
        "캠코더",
        "영상감시장치",
    ]


def test_vendor_item_policy_summary_requires_detail_selection_for_generic_computer():
    checks = [
        {
            "detail_product_code": "4321150701",
            "detail_product_name": "데스크톱컴퓨터",
            "matched_policy_source": "product_policy_summary",
            "is_sme_competition_product": "1",
        },
        {
            "detail_product_code": "5612150801",
            "detail_product_name": "컴퓨터책상",
            "matched_policy_source": "pps_shopping_mall_item_policy_summary",
            "is_sme_competition_product": "",
        },
        {
            "detail_product_code": "4321150102",
            "detail_product_name": "컴퓨터서버",
            "matched_policy_source": "pps_shopping_mall_item_policy_summary",
            "is_sme_competition_product": "",
        },
        {
            "detail_product_code": "55121718",
            "detail_product_name": "데스크톱컴퓨터, 아이엠펀, SB2120, Intel Core i3 2120(3.3GHz), 모니터제외",
            "matched_policy_source": "facility_material_price_file",
            "is_sme_competition_product": "",
        },
        {
            "detail_product_code": "4321150301",
            "detail_product_name": "노트북컴퓨터",
            "matched_policy_source": "pps_shopping_mall_item_policy_summary",
            "is_sme_competition_product": "",
        },
    ]

    summary = api_server._vendor_item_policy_summary("컴퓨터 구매", checks, requested=True)

    assert summary["status"] == "needs_item_selection"
    assert summary["selection_title"] == "컴퓨터 종류 선택 필요"
    assert [item["detail_product_name"] for item in summary["selection_options"]] == [
        "데스크톱컴퓨터",
        "컴퓨터서버",
        "노트북컴퓨터",
    ]


def test_vendor_item_policy_summary_uses_db_item_selection_options(monkeypatch):
    def fake_search_item_selection_options(keyword, limit=12):
        if keyword != "의자":
            return None
        return {
            "selection_title": "의자 세부품명 선택 필요",
            "message": "'의자'만으로는 세부품명을 하나로 확정할 수 없습니다.",
            "meta": {"source": "procurement_product_classification"},
            "selection_options": [
                {
                    "detail_product_code": "5611210201",
                    "detail_product_name": "작업용의자",
                    "active_registered_count": 27283,
                    "active_busan_supplier_count": 5,
                    "matched_policy_source": "pps_shopping_mall_item_policy_summary",
                },
                {
                    "detail_product_code": "5610154201",
                    "detail_product_name": "접이식의자",
                    "active_registered_count": 7393,
                    "active_busan_supplier_count": 4,
                    "matched_policy_source": "pps_shopping_mall_item_policy_summary",
                },
            ],
        }

    monkeypatch.setattr(
        api_server,
        "_vendor_import_company_db",
        lambda: SimpleNamespace(search_item_selection_options=fake_search_item_selection_options),
    )

    summary = api_server._vendor_item_policy_summary(
        "의자 구매",
        [{"detail_product_code": "5611210201", "detail_product_name": "작업용의자", "matched_policy_source": "product_policy_summary"}],
        requested=True,
    )

    assert summary["status"] == "needs_item_selection"
    assert summary["selection_title"] == "의자 세부품명 선택 필요"
    assert [item["detail_product_name"] for item in summary["selection_options"]] == ["작업용의자", "접이식의자"]
    assert summary["selection_options"][0]["shopping_mall_active_busan_supplier_count"] == "5"


def test_vendor_db_item_selection_terms_do_not_widen_specific_phrase(monkeypatch):
    calls = []

    def fake_search_item_selection_options(keyword, limit=12):
        calls.append(keyword)
        if keyword == "컴퓨터":
            return {
                "selection_title": "컴퓨터 세부품명 선택 필요",
                "message": "컴퓨터는 세부품명 선택이 필요합니다.",
                "selection_options": [
                    {"detail_product_name": "데스크톱컴퓨터", "detail_product_code": "4321150701"},
                    {"detail_product_name": "노트북컴퓨터", "detail_product_code": "4321150301"},
                ],
            }
        return None

    monkeypatch.setattr(
        api_server,
        "_vendor_import_company_db",
        lambda: SimpleNamespace(search_item_selection_options=fake_search_item_selection_options),
    )

    assert api_server._vendor_db_item_disambiguation("데스크톱 컴퓨터 구매") is None
    assert calls == ["데스크톱 컴퓨터"]


def test_vendor_payload_blocks_generic_camera_candidates(monkeypatch):
    monkeypatch.setattr(
        api_server,
        "_vendor_recommendation_rows",
        lambda q, region="부산", limit=100, budget_krw=None: [
            {**_sample_vendor_row(), "matched_source": "product"}
        ],
    )
    monkeypatch.setattr(
        api_server,
        "_vendor_product_policy_checks",
        lambda q, limit=5: [
            {
                "detail_product_code": "4617162201",
                "detail_product_name": "영상감시장치",
                "matched_policy_source": "product_policy_summary",
                "is_sme_competition_product": "1",
            }
        ],
    )

    payload = api_server._vendor_recommendation_payload("카메라 구매", limit=10)

    assert payload["count"] == 0
    assert payload["rows"] == []
    assert payload["item_policy_summary"]["status"] == "needs_item_selection"
    assert [item["detail_product_name"] for item in payload["item_policy_summary"]["selection_options"]] == ["영상감시장치"]
    assert payload["zero_result_status"]["status"] == "item_selection_required"
    assert payload["purchase_route_guidance"]["primary_route"]["route_id"] == "item_selection_required"


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


def test_vendor_product_policy_checks_do_not_expand_specific_desktop_to_generic_computer(monkeypatch):
    shopping_calls = []
    policy_calls = []
    facility_calls = []

    def fake_search_shopping_mall_item_policy(keyword, limit=5):
        shopping_calls.append(keyword)
        if keyword == "데스크톱컴퓨터":
            return {
                "candidates": [{
                    "detail_product_code": "4321150701",
                    "detail_product_name": "데스크톱컴퓨터",
                    "active_registered_count": "1723",
                    "active_third_party_count": "1344",
                    "active_mas_count": "379",
                    "active_supplier_count": "23",
                    "active_busan_supplier_count": "0",
                    "active_contract_types": "mas,third_party_unit_price",
                }],
            }
        if keyword == "컴퓨터":
            return {
                "candidates": [{
                    "detail_product_code": "5612150801",
                    "detail_product_name": "컴퓨터책상",
                    "active_registered_count": "3329",
                    "active_busan_supplier_count": "4",
                }],
            }
        return {"candidates": []}

    def fake_search_product_policy(keyword, limit=5):
        policy_calls.append(keyword)
        if keyword == "데스크톱컴퓨터":
            return {
                "meta": {"source": "product_policy_summary"},
                "candidates": [{
                    "detail_product_code": "4321150701",
                    "detail_product_name": "데스크톱컴퓨터",
                    "is_sme_competition_product": "1",
                    "direct_production_valid_supplier_count": "5",
                    "mas_active_supplier_count": "379",
                    "busan_company_product_count": "87",
                }],
            }
        return {"meta": {"source": "product_policy_summary"}, "candidates": []}

    def fake_search_facility_material_policy(keyword, limit=5):
        facility_calls.append(keyword)
        return {
            "candidates": [{
                "detail_product_code": "55121718",
                "detail_product_name": "데스크톱컴퓨터, 아이엠펀, SB2120, Intel Core i3 2120(3.3GHz), 모니터제외",
            }]
        }

    monkeypatch.setattr(
        api_server,
        "_vendor_import_company_db",
        lambda: SimpleNamespace(
            search_facility_material_policy=fake_search_facility_material_policy,
            search_shopping_mall_item_policy=fake_search_shopping_mall_item_policy,
            search_product_policy=fake_search_product_policy,
        ),
    )

    checks = api_server._vendor_product_policy_checks("데스크톱 컴퓨터 구매", limit=5)

    names = [item["detail_product_name"] for item in checks]
    assert names == ["데스크톱컴퓨터"]
    assert facility_calls == []
    assert "컴퓨터" not in shopping_calls
    assert "노트북컴퓨터" not in shopping_calls
    assert "컴퓨터" not in policy_calls


def test_vendor_product_policy_check_gate_skips_service_queries():
    assert api_server._vendor_should_check_product_policy("정품토너 구매 업체") is True
    assert api_server._vendor_should_check_product_policy("데스크톱 컴퓨터 납품 업체") is True
    assert api_server._vendor_should_check_product_policy("번역용역 부산 업체") is False
    assert api_server._vendor_should_check_product_policy("청사 경비용역 부산 업체") is False


def test_vendor_item_evidence_prioritizes_direct_production_for_sme_competition(monkeypatch):
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: SimpleNamespace())
    direct_vendor = {
        **_sample_vendor_row(),
        "company_id": "direct",
        "company_name": "직접생산보유",
        "direct_production_summary": "데스크톱컴퓨터 / 직접생산 / valid",
        "policy_subtypes": "",
        "certified_product_types": "",
        "has_mas": "",
        "has_shopping_mall": "",
    }
    generic_vendor = {
        **_sample_vendor_row(),
        "company_id": "generic",
        "company_name": "일반후보",
        "direct_production_summary": "",
        "direct_production_flags": "",
        "policy_subtypes": "",
        "certified_product_types": "",
        "has_mas": "",
        "has_shopping_mall": "",
    }
    product_policy = [{
        "detail_product_name": "데스크톱컴퓨터",
        "is_sme_competition_product": "1",
        "direct_production_valid_supplier_count": "5",
    }]

    rows = api_server._vendor_apply_item_evidence([generic_vendor, direct_vendor], "데스크탑 구매", product_policy)

    assert rows[0]["company_id"] == "direct"
    assert "직접생산" in rows[0]["purchase_route_fit_summary"]
    assert "직접생산 근거 미확인" in rows[-1]["purchase_route_fit_summary"]


def test_vendor_item_evidence_prioritizes_direct_contract_support_when_no_central_route(monkeypatch):
    monkeypatch.setattr(api_server, "_vendor_import_company_db", lambda: SimpleNamespace())
    generic_vendor = {
        **_sample_vendor_row(),
        "company_id": "generic",
        "company_name": "일반후보",
        "policy_subtypes": "",
        "certified_product_types": "",
        "certified_product_summary": "",
        "procurement_attributes": "",
        "direct_production_summary": "",
        "direct_production_flags": "",
        "has_mas": "",
        "has_shopping_mall": "",
    }
    supported_vendor = {
        **generic_vendor,
        "company_id": "supported",
        "company_name": "지원근거보유",
        "policy_subtypes": "women_company",
        "certified_product_types": "performance_certification",
        "certified_product_summary": "사무용품 / 성능인증 / valid",
        "procurement_attributes": "cooperative_purchase",
    }

    rows = api_server._vendor_apply_item_evidence([generic_vendor, supported_vendor], "사무용품 구매", [])

    assert rows[0]["company_id"] == "supported"
    assert "지역업체 직접계약 지원 근거" in rows[0]["purchase_route_fit_summary"]
    assert "수의계약 지원 근거 미확인" in rows[-1]["purchase_route_fit_summary"]


def test_vendor_item_evidence_filters_broad_camera_mas_matches(monkeypatch):
    def fake_item_evidence(company_ids, terms, limit_per_company=5):
        return {
            "camera-broad": {
                "direct_production": [],
                "mas": [
                    {"detail_product_name": "보안용카메라", "detail_product_code": "4617161002", "status": "active"},
                    {"detail_product_name": "영상감시장치", "detail_product_code": "4617162201", "status": "active"},
                ],
                "shopping_mall": [
                    {"detail_product_name": "카메라브래킷", "detail_product_code": "4512160902", "status": "active"},
                ],
            }
        }

    monkeypatch.setattr(
        api_server,
        "_vendor_import_company_db",
        lambda: SimpleNamespace(search_company_item_evidence=fake_item_evidence),
    )
    row = {
        **_sample_vendor_row(),
        "company_id": "camera-broad",
        "company_name": "카메라군 일반후보",
        "main_products": "CCTV, 보안용카메라",
        "has_mas": "true",
        "has_shopping_mall": "true",
        "mas_product_summary": "보안용카메라 / 4617161002 / MAS / active",
        "shopping_mall_product_summary": "카메라브래킷 / 4512160902 / 쇼핑몰 / active",
    }
    checks = [{
        "detail_product_name": "디지털카메라",
        "detail_product_code": "4512150401",
        "shopping_mall_product_class_code": "45121504",
        "shopping_mall_active_mas_count": "2",
        "shopping_mall_active_registered_count": "2",
        "shopping_mall_active_busan_supplier_count": "0",
    }]

    rows = api_server._vendor_apply_item_evidence([row], "디지털카메라 구매", checks)

    assert rows[0]["mas_match"] == "MAS 근거 없음"
    assert rows[0]["shopping_mall_match"] == "종합쇼핑몰 근거 없음"
    assert "MAS 요청품목 등록 근거 충족" not in rows[0]["purchase_route_fit_summary"]
    assert "종합쇼핑몰 요청품목 등록 근거 충족" not in rows[0]["purchase_route_fit_summary"]
    assert "요청 품목 기준 직생/MAS/쇼핑몰 세부 근거 없음" == rows[0]["requested_item_evidence_summary"]


def test_vendor_policy_item_filter_removes_other_camera_type_candidates():
    rows = [
        {
            **_sample_vendor_row(),
            "company_id": "digital-camera",
            "main_products": "디지털카메라",
            "matched_query": "디지털카메라",
        },
        {
            **_sample_vendor_row(),
            "company_id": "security-camera",
            "main_products": "보안용카메라",
            "matched_query": "카메라",
            "mas_product_summary": "보안용카메라 / 4617161002 / MAS / active",
        },
    ]
    checks = [{
        "detail_product_name": "디지털카메라",
        "detail_product_code": "4512150401",
        "shopping_mall_product_class_code": "45121504",
    }]

    filtered = api_server._vendor_filter_rows_for_policy_item(rows, checks)

    assert [row["company_id"] for row in filtered] == ["digital-camera"]


def test_vendor_purchase_route_guidance_does_not_badge_generic_mas_as_local_supplier():
    row = {
        **_sample_vendor_row(),
        "company_id": "camera-broad",
        "has_mas": "true",
        "has_shopping_mall": "true",
        "mas_product_summary": "보안용카메라 / 4617161002 / MAS / active",
        "shopping_mall_product_summary": "카메라브래킷 / 4512160902 / 쇼핑몰 / active",
        "mas_match": "MAS 근거 없음",
        "shopping_mall_match": "종합쇼핑몰 근거 없음",
    }
    checks = [{
        "detail_product_name": "디지털카메라",
        "detail_product_code": "4512150401",
        "shopping_mall_active_mas_count": "2",
        "shopping_mall_active_registered_count": "2",
        "shopping_mall_active_busan_supplier_count": "0",
    }]

    guidance = api_server._vendor_purchase_route_guidance(
        "디지털카메라 구매",
        [row],
        checks,
        {"status": "matched", "sme_competition_product": "미해당"},
    )
    badge_labels = [badge["label"] for badge in guidance["badges"]]

    assert "조달청 다수공급자계약(MAS) 지역업체 존재" not in badge_labels
    assert "조달청 나라장터 지역업체 존재" not in badge_labels
    assert "다수공급자계약(MAS) 품목" in badge_labels
    assert "부산 MAS/쇼핑몰 공급업체 미확인" in badge_labels
    assert "지역업체 대안 검토" in badge_labels
    assert guidance["shopping_mall_busan_supplier_count"] == 0


def test_vendor_purchase_route_guidance_separates_item_master_and_candidate_supplier_basis():
    row = {
        **_sample_vendor_row(),
        "company_id": "desktop-exact",
        "has_mas": "true",
        "has_shopping_mall": "true",
        "mas_match": "MAS 일치: 데스크톱컴퓨터 4321150701 active",
        "shopping_mall_match": "종합쇼핑몰 일치: 데스크톱컴퓨터 4321150701 active",
    }
    checks = [{
        "detail_product_name": "데스크톱컴퓨터",
        "detail_product_code": "4321150701",
        "matched_policy_source": "pps_shopping_mall_item_policy_summary",
        "shopping_mall_active_third_party_count": "7",
        "shopping_mall_active_registered_count": "12",
        "shopping_mall_active_busan_supplier_count": "0",
    }]

    guidance = api_server._vendor_purchase_route_guidance(
        "데스크톱컴퓨터 구매",
        [row],
        checks,
        {"status": "matched"},
    )
    badge_labels = [badge["label"] for badge in guidance["badges"]]

    assert guidance["purchase_route_basis_label"] == "제3자단가계약 품목으로 확인"
    assert guidance["shopping_mall_busan_supplier_count"] == 0
    assert guidance["shopping_mall_candidate_exact_supplier_count"] == 1
    assert guidance["shopping_mall_local_supplier_basis"] == "candidate_conflict_with_item_master"
    assert "MAS/쇼핑몰 부산업체 존재 확인(DB기준)" not in badge_labels
    assert "부산 MAS/쇼핑몰 공급업체 미확인" in badge_labels
    assert "조달청 다수공급자계약(MAS) 지역업체 존재" not in badge_labels
    assert "조달청 나라장터 지역업체 존재" not in badge_labels
    assert guidance["primary_route"]["status"] == "no_local_supplier"
    assert "물품식별번호, 계약상태, 공급업체 유효 여부를 수동 확인" in guidance["primary_route"]["reason"]


def test_vendor_purchase_route_guidance_adds_regional_direct_contract_support_card():
    rows = [{
        **_sample_vendor_row(),
        "policy_company_labels": "여성기업",
        "policy_subtypes": "women_company",
        "certified_product_labels": "성능인증",
        "certified_product_types": "performance_certification",
        "cooperative_purchase_route_label": "조합추천/소기업 공동사업제품 경로 검토 가능성",
    }]

    guidance = api_server._vendor_purchase_route_guidance(
        "사무용품 구매",
        rows,
        [],
        {"status": "확인 필요"},
        budget_krw=30_000_000,
    )
    cards = {card["route_id"]: card for card in guidance["route_cards"]}

    assert "regional_direct_contract_support" in cards
    assert cards["regional_direct_contract_support"]["route_priority"] == "secondary"
    assert "정책기업" in cards["regional_direct_contract_support"]["practical_note"]


def test_vendor_purchase_route_guidance_does_not_promote_generic_mas_for_service_query():
    rows = [
        api_server._vendor_recommendation_row({
            **_sample_vendor_row(),
            "company_id": "cleaning",
            "company_name": "청소후보",
            "main_products": "청소용역",
            "mas_product_summary": "과거 MAS 근거",
            "shopping_mall_product_summary": "과거 쇼핑몰 근거",
            "has_mas": "true",
            "has_shopping_mall": "true",
        })
    ]

    guidance = api_server._vendor_purchase_route_guidance(
        "청소용역 업체",
        rows,
        [],
        {"status": "not_requested"},
    )

    assert guidance["primary_route"]["route_id"] == "service_contract_review"
    assert all(card["route_id"] != "mas" for card in guidance["route_cards"])
    badge_labels = [badge["label"] for badge in guidance["badges"]]
    assert not any("MAS" in label for label in badge_labels)
    assert not any("\ub098\ub77c\uc7a5\ud130" in label for label in badge_labels)
