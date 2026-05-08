import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from policies.internal_law_discovery import discover_internal_law_hits
from policies.model_routing_policy import generate_mandatory_mcp_plan


def _queries(plan):
    return [item["args"]["query"] for item in plan]


def test_dynamic_discovery_finds_technology_development_purchase_rule():
    hits = discover_internal_law_hits("성능인증 제품으로 2억 물품 수의계약 가능해?", agency_type="default")
    queries = [hit.query for hit in hits]

    assert "중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙" in queries
    assert all("공기업" not in query and "준정부" not in query for query in queries)


def test_dynamic_discovery_augments_fixed_cluster_plan():
    plan = generate_mandatory_mcp_plan("성능인증 제품으로 2억 물품 수의계약 가능해?", 2, agency_type="default")
    queries = _queries(plan)

    assert "지방계약법 시행령 제25조" in queries
    assert "중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙" in queries
    assert any(item.get("selected_reason") == "dynamic_internal_discovery" for item in plan)


def test_dynamic_discovery_handles_mid_term_competition_alias():
    plan = generate_mandatory_mcp_plan(
        "중기간 경쟁 대상이고 직접생산 확인 필요한 제품 수의계약 가능해?",
        2,
        agency_type="default",
    )
    queries = _queries(plan)

    assert "중소기업제품 구매촉진 및 판로지원법 제6조" in queries
    assert "조달청 제조물품 직접생산확인 기준" in queries
    assert "중소기업제품 구매촉진법 시행령 제6조" in queries
