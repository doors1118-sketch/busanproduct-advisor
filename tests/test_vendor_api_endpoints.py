from fastapi.testclient import TestClient

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
