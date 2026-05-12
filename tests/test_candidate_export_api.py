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
