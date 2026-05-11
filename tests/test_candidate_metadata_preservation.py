import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from policies.candidate_policy import classify_candidates
from policies.candidate_formatter import format_candidate_tables


def test_classify_candidates_uses_raw_result_when_result_is_formatted_text():
    raw_candidate = {
        "company_id": "pc-1",
        "company_name": "부산컴퓨터",
        "location": "부산광역시",
        "main_products": ["데스크톱컴퓨터"],
        "candidate_types": ["shopping_mall_supplier"],
        "primary_candidate_type": "shopping_mall_supplier",
        "shopping_mall_flags": ["mas_registered", "shopping_mall_registered"],
    }
    tool_results = [
        {
            "tool_name": "search_shopping_mall",
            "status": "success",
            "result": "부산 지역업체 검색 결과: 총 1건\n\n1. 부산컴퓨터 (부산광역시) [영업중]\n   품목: 데스크톱컴퓨터",
            "raw_result": {"candidates": [raw_candidate]},
        }
    ]

    classified = classify_candidates(tool_results, "예산 6천만원으로 컴퓨터 구매")
    table = format_candidate_tables(classified, "예산 6천만원으로 컴퓨터 구매")

    assert classified["shopping_mall_supplier"][0]["company_name"] == "부산컴퓨터"
    assert "| 쇼핑몰 | 부산컴퓨터 | 부산광역시 | 데스크톱컴퓨터 | 확인 | MAS, 종합쇼핑몰 |" in table


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
    assert "통합교통시스템 v1.0" not in table
    assert "| 정책기업 | 주식회사 유니시큐 | 부산광역시 | 보안용카메라 | 확인 |" in table
    assert "| 정책기업 | 주식회사 유니시큐" in table
    assert "9999-12-31" not in table
    assert "smpp_tech_product_api" not in table
    assert "priority_purchase_product" not in table


def test_candidate_only_cctv_answer_suppresses_contract_routes_and_groups_strengths():
    classified = {
        "shopping_mall_supplier": [
            {
                "company_id": "cctv-1",
                "company_name": "주식회사 예스텍",
                "location": "부산광역시",
                "main_products": ["CCTV카메라"],
                "candidate_types": ["local_procurement_company", "shopping_mall_supplier", "priority_purchase_product"],
                "primary_candidate_type": "shopping_mall_supplier",
                "shopping_mall_registered": True,
                "shopping_mall_flags": ["mas_registered", "shopping_mall_registered"],
                "certified_product_types": ["gs_certified_product"],
                "sme_competition_product": True,
                "manufacturer_type": "manufacture",
                "license_or_business_type": ["정보통신공사업", "소프트웨어사업자(컴퓨터관련서비스사업)"],
                "purchase_routes": ["수의계약 검토", "2인 이상 견적 검토"],
            }
        ],
        "local_procurement_company": [
            {
                "company_id": "cctv-2",
                "company_name": "(주)선진텔레콤",
                "location": "부산광역시",
                "main_products": ["CCTV카메라"],
                "candidate_types": ["local_procurement_company"],
                "primary_candidate_type": "local_procurement_company",
                "sme_competition_product": True,
                "manufacturer_type": "manufacture",
                "license_or_business_type": ["정보통신공사업", "소프트웨어사업자(컴퓨터관련서비스사업)"],
                "purchase_routes": ["수의계약 검토", "2인 이상 견적 검토"],
            },
            {
                "company_id": "cctv-3",
                "company_name": "주식회사 리더캠",
                "location": "부산광역시",
                "main_products": ["영상감시장치"],
                "candidate_types": ["local_procurement_company"],
                "primary_candidate_type": "local_procurement_company",
                "license_or_business_type": ["정보통신공사업"],
                "purchase_routes": ["수의계약 검토"],
            },
        ],
        "policy_company": [],
        "innovation_product": [],
        "priority_purchase_product": [],
    }

    table = format_candidate_tables(
        classified,
        "CCTV 부산업체 후보만 간단히 찾아줘. 계약 가능 여부 판단은 빼줘.",
    )

    assert "계약 가능 여부 판단은 제외" in table
    assert "제조·기술개발 강점 후보" in table
    assert "설치·SI/정보통신공사 강점 후보" in table
    assert "주식회사 예스텍" in table
    assert "(주)선진텔레콤" in table
    assert "주식회사 리더캠" in table
    assert "영상감시장치" in table
    assert "GS인증" in table
    assert "정보통신공사업" in table
    assert "검토 가능 경로" not in table
    assert "수의계약 검토" not in table
    assert "2인 이상 견적" not in table
    assert "구매 경로별" not in table


def test_irrelevant_certified_product_candidates_are_filtered_by_item():
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

    assert classified["priority_purchase_product"] == []
    assert "이륜차 배달경로 시스템 v1.0" not in table
    assert "GS인증" not in table


def test_relevant_certified_product_candidates_are_displayed_in_production():
    raw_candidate = {
        "company_id": "x3",
        "company_name": "주식회사 엘이디",
        "location": "부산광역시",
        "main_products": ["LED 조명"],
        "candidate_types": ["local_procurement_company", "priority_purchase_product"],
        "certified_product_types": ["gs_certified_product"],
        "certified_product_summary": [
            {
                "certification_type": "gs_certified_product",
                "product_name": "LED 조명 제어장치 v1.0",
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
    assert "LED 조명 제어장치 v1.0" in table
    assert "GS인증" in table


def test_candidate_formatter_hides_policy_company_table_when_route_excludes_it():
    classified = {
        "shopping_mall_supplier": [
            {
                "company_name": "부산컴퓨터",
                "location": "부산광역시",
                "main_products": ["컴퓨터"],
                "candidate_types": ["shopping_mall_supplier"],
                "primary_candidate_type": "shopping_mall_supplier",
                "shopping_mall_registered": True,
                "purchase_routes": ["종합쇼핑몰 구매"],
                "note": "후보",
            }
        ],
        "local_procurement_company": [],
        "policy_company": [
            {
                "company_name": "정책컴퓨터",
                "location": "부산광역시",
                "main_products": ["컴퓨터"],
                "candidate_types": ["policy_company"],
                "primary_candidate_type": "policy_company",
                "policy_tags": ["여성기업"],
                "purchase_routes": ["정책기업 수의계약 검토"],
                "note": "후보",
            }
        ],
        "innovation_product": [],
        "priority_purchase_product": [],
    }

    table = format_candidate_tables(
        classified,
        "예산 6천만원으로 컴퓨터 구매하고 싶다",
        hidden_candidate_types={"policy_company"},
        preferred_order=["shopping_mall_supplier"],
    )

    assert "나라장터 종합쇼핑몰 등록 부산업체 후보" in table
    assert "정책기업 수의계약 검토 후보" not in table
    assert "정책컴퓨터" not in table


def test_candidate_formatter_keeps_hidden_type_when_user_explicitly_asks():
    classified = {
        "shopping_mall_supplier": [],
        "local_procurement_company": [],
        "policy_company": [
            {
                "company_name": "정책컴퓨터",
                "location": "부산광역시",
                "main_products": ["컴퓨터"],
                "candidate_types": ["policy_company"],
                "primary_candidate_type": "policy_company",
                "policy_tags": ["여성기업"],
                "purchase_routes": ["정책기업 수의계약 검토"],
                "note": "후보",
            }
        ],
        "innovation_product": [],
        "priority_purchase_product": [],
    }

    table = format_candidate_tables(
        classified,
        "여성기업 컴퓨터 업체도 보여줘",
        hidden_candidate_types={"policy_company"},
    )

    assert "정책기업 수의계약 검토 후보" in table
    assert "정책컴퓨터" in table
