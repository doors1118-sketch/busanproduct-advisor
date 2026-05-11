import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from policies.purchase_route_guidance_policy import format_purchase_route_guidance_for_llm


def test_route_candidate_counts_use_requested_item_relevance():
    context = format_purchase_route_guidance_for_llm(
        amount=60_000_000,
        item_name="컴퓨터",
        contract_object="goods",
        agency_type="local_government",
        tool_results=[
            {
                "tool_name": "search_certified_product",
                "status": "success",
                "result": "총 1건\n1. 운송관리시스템 v1.0",
                "raw_result": {
                    "candidates": [
                        {
                            "company_name": "무관업체",
                            "product_name": "운송관리시스템 v1.0",
                            "candidate_types": ["priority_purchase_product"],
                        }
                    ]
                },
            },
            {
                "tool_name": "search_shopping_mall",
                "status": "success",
                "result": "총 1건\n1. 컴퓨터업체",
                "raw_result": {
                    "candidates": [
                        {
                            "company_name": "컴퓨터업체",
                            "main_products": ["데스크톱컴퓨터"],
                            "candidate_types": ["shopping_mall_supplier"],
                        }
                    ]
                },
            },
        ],
    )

    assert "| 1순위 | 종합쇼핑몰(MAS) 직접구매 | 중기제품 직접구매 우선 |" in context
    assert "| 2순위 | 지역제한 2인견적 | 검토 가능 |" in context
    assert "| 참고 | 인증제품 | 후보 미확인 |" in context
