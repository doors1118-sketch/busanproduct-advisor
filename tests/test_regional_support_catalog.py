from app.policies.regional_support_catalog import (
    build_catalog_evidence_plan,
    format_catalog_matches_for_llm,
    match_regional_support_catalog,
)
from app.policies.model_routing_policy import generate_mandatory_mcp_plan


def _ids(matches):
    return {m.scheme.id for m in matches}


def test_service_local_purchase_auto_selects_support_schemes():
    matches = match_regional_support_catalog(
        "8천만원 청소용역을 부산업체로 맡길 방법이 있어?",
        contract_object="service",
    )

    ids = _ids(matches)
    assert "small_value_direct_contract" in ids
    assert "policy_company_direct_contract" in ids
    assert "regional_restriction_bid" in ids
    assert "regional_company_evaluation_points" in ids
    assert "shopping_mall_mas_regional_factor" not in ids


def test_construction_local_purchase_auto_selects_joint_and_evaluation():
    matches = match_regional_support_catalog(
        "2억원 전기공사에서 부산 지역업체 수주를 늘릴 방법은?",
        contract_object="construction",
    )

    ids = _ids(matches)
    assert "regional_restriction_bid" in ids
    assert "regional_joint_contract" in ids
    assert "regional_company_evaluation_points" in ids
    assert "technology_development_priority_purchase" not in ids


def test_goods_local_purchase_auto_selects_mas_certification_and_innovation_paths():
    matches = match_regional_support_catalog(
        "8천만원 LED 조명을 부산업체로 구매할 방법이 있어?",
        contract_object="goods",
    )

    ids = _ids(matches)
    assert "regional_restriction_bid" in ids
    assert "shopping_mall_mas_regional_factor" in ids
    assert "technology_development_priority_purchase" in ids
    assert "innovation_product_purchase" in ids
    assert "sme_competition_direct_production" in ids


def test_catalog_evidence_plan_has_selected_reason_and_scheme_metadata():
    plan = build_catalog_evidence_plan(
        "8천만원 청소용역을 부산업체로 맡길 방법이 있어?",
        contract_object="service",
    )

    assert plan
    assert any(item["selected_reason"].startswith("regional_support_catalog:") for item in plan)
    assert any(item.get("catalog_scheme_name") == "지역제한경쟁입찰" for item in plan)


def test_model_plan_is_augmented_with_catalog_entries():
    plan = generate_mandatory_mcp_plan(
        "8천만원 청소용역을 부산업체로 맡길 방법이 있어?",
        2,
        agency_type="default",
    )

    reasons = [item.get("selected_reason", "") for item in plan]
    queries = [(item.get("args") or {}).get("query", "") for item in plan]
    assert any(reason.startswith("regional_support_catalog:") for reason in reasons)
    assert any("지역제한" in query for query in queries)
    assert any("수의계약" in query for query in queries)


def test_catalog_llm_context_tells_llm_to_surface_implicit_schemes():
    context = format_catalog_matches_for_llm(
        "8천만원 청소용역을 부산업체로 맡길 방법이 있어?",
        contract_object="service",
    )

    assert "지역업체 보호·우대제도 카탈로그 매칭" in context
    assert "사용자가 제도를 직접 언급하지 않았더라도" in context
    assert "지역제한경쟁입찰" in context


def test_catalog_evidence_plan_switches_to_national_contract_sources():
    plan = build_catalog_evidence_plan(
        "8천만원 청소용역을 부산업체로 맡길 방법이 있어?",
        contract_object="service",
        agency_type="national_agency",
    )

    queries = [(item.get("args") or {}).get("query", "") for item in plan]
    assert any("국가계약법 시행령 제26조" in query for query in queries)
    assert any("국가계약법 시행령 제21조" in query for query in queries)
    assert any(item.get("catalog_agency_type") == "national_agency" for item in plan)


def test_catalog_evidence_plan_switches_to_public_corporation_sources():
    plan = build_catalog_evidence_plan(
        "20억원 건설공사에 지역업체 공동도급과 가점을 검토해줘",
        contract_object="construction",
        agency_type="public_corporation",
    )

    queries = [(item.get("args") or {}).get("query", "") for item in plan]
    assert any("공기업 준정부기관 계약사무규칙" in query for query in queries)
    assert any("국가계약법 시행령 제72조" in query for query in queries)
    assert any(item.get("catalog_agency_type") == "public_corporation" for item in plan)
