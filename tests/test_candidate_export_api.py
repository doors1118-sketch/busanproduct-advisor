import sys
from pathlib import Path
from types import SimpleNamespace


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import api_server


def test_candidate_export_xlsx_contains_query_basis_and_company_rows(monkeypatch):
    def search_by_product(term, limit=200):
        if term == "잔디":
            return {
                "candidates": [
                    {
                        "company_id": "turf-1",
                        "company_name": "(주)카람",
                        "location": "부산광역시",
                        "license_or_business_type": ["조경식재ㆍ시설물공사업"],
                        "main_products": ["잔디"],
                        "policy_subtypes": [],
                        "shopping_mall_flags": [],
                    }
                ]
            }
        if term == "복합비료":
            return {
                "candidates": [
                    {
                        "company_id": "eco-green",
                        "company_name": "주식회사     에코그린",
                        "location": "부산광역시",
                        "license_or_business_type": ["조경식재공사업"],
                        "main_products": ["복합비료"],
                        "policy_subtypes": ["women_company"],
                        "shopping_mall_flags": [],
                    }
                ]
            }
        return {"candidates": []}

    fake_company_db = SimpleNamespace(
        search_by_product=search_by_product,
        search_by_license=lambda term, limit=200: {"candidates": []},
        search_by_company_name=lambda term, limit=200: {"candidates": []},
    )
    monkeypatch.setitem(sys.modules, "company_db", fake_company_db)

    content = api_server._build_candidate_export_xlsx(
        "1억원으로 학교 운동장 천연잔디 조성공사를 하려고 하는데 계약방법, 면허요건, 부산업체 후보를 알려줘"
    )

    assert content
    assert b"PK" in content[:4]
    rows = api_server._generic_candidate_export_rows("학교 운동장 천연잔디 조성공사 부산업체 후보")
    assert any(row["업체명"] == "(주)카람" and row["조회기준"] == "품목: 잔디" for row in rows)
    assert any(row["업체명"] == "주식회사     에코그린" and "여성기업" in row["정책기업"] for row in rows)


def test_candidate_export_xlsx_contains_security_service_license_rows(monkeypatch):
    def search_by_license(term, limit=200):
        if term == "시설경비업무":
            return {
                "candidates": [
                    {
                        "company_id": "security-1",
                        "company_name": "부산보안테스트",
                        "location": "부산광역시",
                        "license_or_business_type": ["시설경비업무", "기계경비업무"],
                        "main_products": ["시설물경비서비스"],
                        "policy_subtypes": ["women_company"],
                        "shopping_mall_flags": [],
                    }
                ]
            }
        return {"candidates": []}

    fake_company_db = SimpleNamespace(
        search_by_product=lambda term, limit=200: {"candidates": []},
        search_by_license=search_by_license,
        search_by_company_name=lambda term, limit=200: {"candidates": []},
    )
    monkeypatch.setitem(sys.modules, "company_db", fake_company_db)

    content = api_server._build_candidate_export_xlsx(
        "청사 경비용역을 부산업체 중심으로 검토하려면 지역제한과 면허를 어떻게 봐야 해?"
    )

    assert content
    assert b"PK" in content[:4]
    rows = api_server._generic_candidate_export_rows("청사 경비용역 부산업체 후보")
    assert any(row["업체명"] == "부산보안테스트" and row["조회기준"] == "면허: 시설경비업무" for row in rows)
    assert any("여성기업" in row["정책기업"] for row in rows)


def test_candidate_export_xlsx_contains_event_service_product_rows(monkeypatch):
    def search_by_product(term, limit=200):
        if term == "기타행사기획및대행서비스":
            return {
                "candidates": [
                    {
                        "company_id": "event-1",
                        "company_name": "부산행사기획",
                        "location": "부산광역시",
                        "license_or_business_type": [],
                        "main_products": ["기타행사기획및대행서비스"],
                        "policy_subtypes": ["social_enterprise"],
                        "shopping_mall_flags": [],
                    }
                ]
            }
        return {"candidates": []}

    fake_company_db = SimpleNamespace(
        search_by_product=search_by_product,
        search_by_license=lambda term, limit=200: {"candidates": []},
        search_by_company_name=lambda term, limit=200: {"candidates": []},
    )
    monkeypatch.setitem(sys.modules, "company_db", fake_company_db)

    assert api_server._candidate_export_requested("발대식 행사 용역 예산 2억원으로 계약 방법 안내")
    content = api_server._build_candidate_export_xlsx("발대식 행사 용역 예산 2억원으로 계약 방법 안내")

    assert content
    assert b"PK" in content[:4]
    rows = api_server._generic_candidate_export_rows("발대식 행사 용역 예산 2억원으로 계약 방법 안내")
    assert any(row["업체명"] == "부산행사기획" and row["조회기준"] == "품목: 기타행사기획및대행서비스" for row in rows)
    assert any("사회적기업" in row["정책기업"] for row in rows)
