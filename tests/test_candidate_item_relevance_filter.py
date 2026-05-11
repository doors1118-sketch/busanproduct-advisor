import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from policies.candidate_formatter import (
    candidate_matches_user_item,
    filter_candidate_rows_by_user_item,
    format_candidate_tables,
)


def test_computer_question_filters_out_unrelated_supplier_rows():
    computer_row = {
        "company_id": "computer-1",
        "company_name": "컴퓨터업체",
        "location": "부산광역시",
        "main_products": ["데스크톱컴퓨터", "컴퓨터서버"],
        "candidate_types": ["shopping_mall_supplier"],
        "primary_candidate_type": "shopping_mall_supplier",
        "shopping_mall_registered": True,
        "shopping_mall_flags": ["mas_registered"],
    }
    furniture_row = {
        "company_id": "furniture-1",
        "company_name": "가구업체",
        "location": "부산광역시",
        "main_products": ["크레덴자", "파일링캐비닛", "교탁"],
        "candidate_types": ["shopping_mall_supplier"],
        "primary_candidate_type": "shopping_mall_supplier",
        "shopping_mall_registered": True,
        "shopping_mall_flags": ["mas_registered"],
    }

    classified = {
        "shopping_mall_supplier": [computer_row, furniture_row],
        "local_procurement_company": [],
        "policy_company": [],
        "innovation_product": [],
        "priority_purchase_product": [],
    }
    rendered = format_candidate_tables(classified, "예산 6천만원으로 컴퓨터를 구매하려고 해")

    assert "컴퓨터업체" in rendered
    assert "가구업체" not in rendered
    assert "크레덴자" not in rendered


def test_computer_question_filters_out_unrelated_certified_products():
    unrelated_cert = {
        "company_id": "cert-1",
        "company_name": "자동화설비업체",
        "location": "부산광역시",
        "product_name": "논스톱 결제 및 비대면 서비스 기반의 역무자동화설비 개발",
        "candidate_types": ["priority_purchase_product"],
        "primary_candidate_type": "priority_purchase_product",
        "certified_product_types": ["demand_designated_tech_product"],
    }
    relevant_cert = {
        "company_id": "cert-2",
        "company_name": "서버업체",
        "location": "부산광역시",
        "product_name": "컴퓨터서버 관리시스템",
        "candidate_types": ["priority_purchase_product"],
        "primary_candidate_type": "priority_purchase_product",
        "certified_product_types": ["gs_certified_product"],
    }

    rows = filter_candidate_rows_by_user_item([unrelated_cert, relevant_cert], "컴퓨터 구매")

    assert rows == [relevant_cert]
    assert not candidate_matches_user_item(unrelated_cert, "컴퓨터 구매")


def test_certified_product_row_must_match_visible_product_name_not_company_catalog():
    row = {
        "company_id": "cert-3",
        "company_name": "컴퓨터도취급하는업체",
        "location": "부산광역시",
        "product_name": "운송관리시스템 v1.0",
        "main_products": ["데스크톱컴퓨터", "컴퓨터서버"],
        "candidate_types": ["priority_purchase_product"],
        "primary_candidate_type": "priority_purchase_product",
        "certified_product_types": ["gs_certified_product"],
    }

    assert not candidate_matches_user_item(row, "컴퓨터 구매")
    assert not candidate_matches_user_item(row, "컴퓨터 구매", candidate_type="priority_purchase_product")


def test_certified_product_filter_infers_type_from_candidate_types_for_export_path():
    row = {
        "company_id": "cert-4",
        "company_name": "컴퓨터도취급하는업체",
        "location": "부산광역시",
        "product_name": "운송관리시스템 v2.0",
        "main_products": ["데스크톱컴퓨터", "컴퓨터서버"],
        "candidate_types": ["local_procurement_company", "priority_purchase_product"],
        "certified_product_types": ["gs_certified_product"],
    }

    assert not candidate_matches_user_item(row, "컴퓨터 구매")


def test_company_table_uses_registered_product_names_and_escapes_markdown_pipes():
    row = {
        "company_id": "mall-1",
        "company_name": "부산컴퓨터|테스트",
        "location": "부산광역시",
        "registered_product_names": ["데스크톱컴퓨터|고급형"],
        "candidate_types": ["shopping_mall_supplier"],
        "primary_candidate_type": "shopping_mall_supplier",
        "shopping_mall_registered": True,
        "shopping_mall_flags": ["mas_registered"],
    }
    classified = {
        "shopping_mall_supplier": [row],
        "local_procurement_company": [],
        "policy_company": [],
        "innovation_product": [],
        "priority_purchase_product": [],
    }

    rendered = format_candidate_tables(classified, "컴퓨터 구매")

    assert "부산컴퓨터/테스트" in rendered
    assert "데스크톱컴퓨터/고급형" in rendered
    assert "MAS" in rendered


def test_translation_service_question_keeps_query_specific_company_candidates():
    local_row = {
        "company_id": "translation-local-1",
        "company_name": "부산번역센터",
        "location": "부산광역시 해운대구",
        "main_products": [],
        "candidate_types": ["local_procurement_company"],
        "primary_candidate_type": "local_procurement_company",
        "purchase_routes": ["2인 이상 견적 검토", "지역제한 입찰 검토"],
    }
    policy_row = {
        "company_id": "translation-policy-1",
        "company_name": "부산통번역협동조합",
        "location": "부산광역시 부산진구",
        "main_products": [],
        "candidate_types": ["policy_company"],
        "primary_candidate_type": "policy_company",
        "policy_tags": ["social_cooperative"],
        "purchase_routes": ["정책기업 수의계약 검토", "2인 이상 견적 검토"],
    }
    classified = {
        "shopping_mall_supplier": [],
        "local_procurement_company": [local_row],
        "policy_company": [policy_row],
        "innovation_product": [],
        "priority_purchase_product": [],
    }

    rendered = format_candidate_tables(
        classified,
        "번역용역 4천만원에서 부산업체 우대 조건을 계약방식과 평가항목 관점에서 검토해줘",
    )

    assert "부산번역센터" in rendered
    assert "부산통번역협동조합" in rendered
    assert "2인 이상 견적 검토" in rendered
    assert "사회적협동조합" in rendered
