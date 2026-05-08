import sys
from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from internal_law_lookup import search_internal_annexes
from policies.model_routing_policy import generate_mandatory_mcp_plan
from policies.tool_orchestration_policy import augment_tool_orchestration


def _tools(plan):
    return [item["name"] for item in plan]


def test_regional_restriction_adds_law_system_chain_after_cluster_plan():
    plan = generate_mandatory_mcp_plan("지역제한경쟁입찰 기준의 법체계를 알려줘", 2, agency_type="default")

    assert "chain_law_system" in _tools(plan)
    assert any(
        item.get("selected_reason") == "tool_orchestration:law_system_chain"
        for item in plan
    )


def test_case_or_interpretation_question_adds_full_research():
    base_plan = [{"name": "search_law", "args": {"query": "지방계약법 시행령 제25조"}}]

    plan = augment_tool_orchestration("수의계약 관련 감사 지적 사례나 해석례가 있어?", base_plan)

    assert "chain_full_research" in _tools(plan)
    assert any(
        item.get("selected_reason") == "tool_orchestration:interpretation_case_or_audit"
        for item in plan
    )


def test_annex_question_adds_get_annexes_with_law_name_key():
    base_plan = [{"name": "search_law", "args": {"query": "지방계약법 시행령 제20조"}}]

    plan = augment_tool_orchestration("지역제한 금액 기준 별표를 보여줘", base_plan)
    annex_items = [item for item in plan if item["name"] == "get_annexes"]

    assert annex_items
    assert annex_items[0]["args"]["law_name"] == "지방계약법 시행령"
    assert annex_items[0]["selected_reason"] == "tool_orchestration:annex_or_form_lookup"


def test_internal_admin_rule_annex_lookup_uses_attachment_metadata():
    result = search_internal_annexes("지방자치단체 입찰 및 계약집행기준")

    assert result is not None
    assert "[내부DB]" in result
    assert "첨부파일" in result


def test_internal_law_annex_lookup_uses_collected_annex_db():
    result = search_internal_annexes("중소기업제품 구매촉진법 시행령", annex_no="별표 1")

    assert result is not None
    assert "[내부DB]" in result
    assert "중견기업의 중소기업자간 경쟁입찰에의 참여 제한기준" in result


def test_internal_admin_rule_annex_lookup_uses_xml_annex_text():
    result = search_internal_annexes("물품 다수공급자계약 업무처리규정")

    assert result is not None
    assert "[내부DB]" in result
    assert "적격성 평가 세부기준" in result
