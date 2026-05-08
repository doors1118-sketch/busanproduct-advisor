import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from policies.candidate_policy import classify_candidates
from policies.candidate_formatter import format_candidate_tables


def test_shopping_mall_candidate_preserves_mas_policy_and_cert_metadata():
    raw_candidate = {
        "company_id": "x1",
        "company_name": "주식회사 유니시큐",
        "location": "부산광역시",
        "main_products": ["보안용카메라"],
        "candidate_types": [
            "local_procurement_company",
            "shopping_mall_supplier",
            "policy_company",
            "priority_purchase_product",
        ],
        "primary_candidate_type": "local_procurement_company",
        "shopping_mall_flags": [
            "third_party_unit_price_registered",
            "excellent_procurement_registered",
            "mas_registered",
            "shopping_mall_registered",
        ],
        "shopping_mall_product_summary": [
            {
                "product_name": "광송신기또는수신기",
                "shopping_mall_contract_type": "third_party_unit_price",
                "contract_status": "active",
                "contract_end_date": "20271107",
            }
        ],
        "policy_subtypes": ["women_company"],
        "policy_validity_summary": {"women_company": "valid"},
        "certified_product_types": ["gs_certified_product"],
        "certified_product_summary": [
            {
                "certification_type": "gs_certified_product",
                "product_name": "통합교통시스템 v1.0",
                "validity_status": "valid",
                "expiration_date": "9999-12-31",
            }
        ],
    }
    tool_results = [
        {
            "tool_name": "search_shopping_mall",
            "status": "success",
            "result": json.dumps({"candidates": [raw_candidate]}, ensure_ascii=False),
        }
    ]

    classified = classify_candidates(tool_results, "CCTV 부산업체 추천해줘")
    table = format_candidate_tables(classified, "CCTV 부산업체 추천해줘")

    assert classified["shopping_mall_supplier"][0]["primary_candidate_type"] == "shopping_mall_supplier"
    assert classified["policy_company"][0]["primary_candidate_type"] == "policy_company"
    assert classified["priority_purchase_product"][0]["primary_candidate_type"] == "priority_purchase_product"
    assert "제3자단가" in table
    assert "MAS" in table
    assert "여성기업" in table
    assert "GS인증" in table
    assert "통합교통시스템 v1.0" in table
    assert "| 쇼핑몰 | 주식회사 유니시큐 | 부산광역시 | 광송신기또는수신기 | 확인 |" in table
    assert "| 정책기업 | 주식회사 유니시큐" in table
    assert "9999-12-31" not in table
    assert "smpp_tech_product_api" not in table
    assert "priority_purchase_product" not in table


def test_certified_product_candidates_are_displayed_in_production():
    raw_candidate = {
        "company_id": "x2",
        "company_name": "주식회사 피엘지",
        "location": "부산광역시",
        "main_products": ["정보시스템개발서비스"],
        "candidate_types": ["local_procurement_company", "priority_purchase_product"],
        "certified_product_types": ["gs_certified_product"],
        "certified_product_summary": [
            {
                "certification_type": "gs_certified_product",
                "product_name": "이륜차 배달경로 시스템 v1.0",
                "validity_status": "valid",
                "expiration_date": "9999-12-31",
            }
        ],
    }
    tool_results = [
        {
            "tool_name": "search_certified_product",
            "status": "success",
            "result": json.dumps({"candidates": [raw_candidate]}, ensure_ascii=False),
        }
    ]

    classified = classify_candidates(tool_results, "LED 기술개발제품 부산업체")
    table = format_candidate_tables(classified, "LED 기술개발제품 부산업체")

    assert classified["priority_purchase_product"]
    assert "기술개발제품 13종" in table
    assert "이륜차 배달경로 시스템 v1.0" in table
    assert "GS인증" in table
