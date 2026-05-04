import pytest
from app.gateway.models.context import GatewayResponse, SourceContext, RouteContext, ProcedureContext, ItemEligibilityResult, GatewayMetadata, SourceEntry, ProcedureSourceEntry, ItemEligibilityContext, CompanyCandidateContext
from app.rule_engine.engine import execute_rule_engine

def get_base_gateway_response() -> GatewayResponse:
    # 빈 GatewayResponse 모의 객체
    return GatewayResponse(
        request_id="test-1234",
        source_context=SourceContext(
            sources=[SourceEntry("S1", "지방계약법", "지방계약법", "law", "law", "local_government", True, "active")],
            assumed_buyer_type=None,
            assumption_reason=None,
            buyer_type_confidence="high",
            required_slots_missing=[]
        ),
        route_context=RouteContext(
            base_jurisdiction="local_contract",
            overlay_applied=False,
            overlay_scope=None,
            overlay_sources=[],
            dual_routing=False
        ),
        procedure_context=ProcedureContext(
            sources=[ProcedureSourceEntry("P1", "조달절차", "procedure", "general", "procedure_guidance_only")],
            filter_applied=False,
            usage="answer_builder_procedure_section_only",
            judgment_eligible=False
        ),
        item_eligibility_result=ItemEligibilityResult(
            resolver_status="not_triggered",
            unavailable_reason=None,
            context=None
        ),
        metadata=GatewayMetadata(
            total_sources_matched=1,
            procedure_sources_matched=1,
            overlay_applied=False,
            item_eligibility_resolver_status="not_triggered",
            item_eligibility_trigger_grade=None,
            company_candidates_found=0,
            enrichment_applied=False,
            enrichment_scope=None
        ),
        company_candidate_context=None
    )

def test_buyer_type_missing_leads_to_insufficient_data():
    resp = get_base_gateway_response()
    resp.source_context.buyer_type_confidence = "low"
    
    ctx = execute_rule_engine(resp)
    assert ctx.review_outcome == "insufficient_data"
    assert "buyer_type" in ctx.missing_required_slots
    assert ctx.buyer_type_assumed is True
    assert ctx.legal_conclusion == "not_determined"

def test_mas_overlay_and_explicit_item():
    resp = get_base_gateway_response()
    resp.route_context.overlay_applied = True
    resp.item_eligibility_result.resolver_status = "resolved"
    resp.item_eligibility_result.context = ItemEligibilityContext(
        item_eligibility_required=True,
        trigger_grade="explicit",
        triggered_by=["T1_keyword"],
        detail_item_resolved=True,
        detail_item_code="1234",
        detail_item_name="CCTV",
        detail_item_candidates=None,
        is_sme_competition_product=True,
        direct_production_required=True,
        company_cert_status="valid",
        eligibility_status=None,
        candidate_action=None
    )
    
    ctx = execute_rule_engine(resp)
    assert ctx.review_outcome == "review_candidate"
    assert ctx.dual_routing_active is True
    assert ctx.route_directive == "base_law_plus_pps_overlay_review"
    assert ctx.item_action_required == "verify_direct_production_cert"
    assert ctx.legal_conclusion == "not_determined"
    assert ctx.enrichment_judgment_effect == "none"

def test_ambiguous_leads_to_manual_review():
    resp = get_base_gateway_response()
    resp.item_eligibility_result.resolver_status = "ambiguous"
    
    ctx = execute_rule_engine(resp)
    assert ctx.review_outcome == "manual_review_required"
    assert "detail_item_code_ambiguous" in ctx.manual_review_reasons
    assert ctx.legal_conclusion == "not_determined"
    assert ctx.item_eligibility_status == "ambiguous"

def test_procedure_context_not_in_applied_sources():
    resp = get_base_gateway_response()
    ctx = execute_rule_engine(resp)
    assert "P1" in ctx.procedure_source_ids
    assert "P1" not in ctx.applied_source_ids
    assert "S1" in ctx.applied_source_ids

def test_enrichment_judgment_effect_is_none():
    resp = get_base_gateway_response()
    resp.company_candidate_context = CompanyCandidateContext(
        candidates=[],
        enrichment_applied=True,
        enrichment_scope="specific_item",
        total_found=1
    )
    ctx = execute_rule_engine(resp)
    assert ctx.enrichment_available is True
    assert ctx.enrichment_judgment_effect == "none"

def test_forbidden_phrases_not_included():
    resp = get_base_gateway_response()
    ctx = execute_rule_engine(resp)
    
    ctx_str = str(ctx)
    
    forbidden_phrases = [
        "계약 가능합니다",
        "구매 가능합니다",
        "수의계약 가능합니다",
        "지역제한 가능합니다",
        "낙찰 가능합니다"
    ]
    
    for phrase in forbidden_phrases:
        assert phrase not in ctx_str

def test_local_purchase_support_mapping_goods_direct():
    gw = get_base_gateway_response()
    request_slots = {
        "contract_object": "goods",
        "contract_method": "direct_contract"
    }
    ctx = execute_rule_engine(gw, request_slots)
    assert ctx.local_purchase_support_review_required is True
    assert "지역제한 경쟁입찰 검토" in ctx.local_purchase_support_tools
    assert "수의계약 활용 가능성 검토" in ctx.local_purchase_support_tools
    assert "지역상품 우선구매 조례·시책 검토" in ctx.local_purchase_support_tools
    
def test_local_purchase_support_mapping_construction():
    gw = get_base_gateway_response()
    request_slots = {
        "contract_object": "construction"
    }
    ctx = execute_rule_engine(gw, request_slots)
    assert "지역의무공동도급 검토" in ctx.local_purchase_support_tools
    assert "지역업체 참여도 가점 검토" in ctx.local_purchase_support_tools

def test_local_purchase_support_mapping_mas():
    gw = get_base_gateway_response()
    request_slots = {
        "procurement_route": "mas"
    }
    ctx = execute_rule_engine(gw, request_slots)
    assert "MAS·종합쇼핑몰 내 지역업체 후보 활용 검토" in ctx.local_purchase_support_tools

def test_local_purchase_support_mapping_explicit_item():
    gw = get_base_gateway_response()
    gw.item_eligibility_result = ItemEligibilityResult(
        resolver_status="resolved",
        unavailable_reason=None,
        context=ItemEligibilityContext(
            trigger_grade="explicit",
            triggered_by=["direct_production"],
            detail_item_resolved=True,
            detail_item_code="12345678",
            detail_item_name="test",
            detail_item_candidates=None,
            is_sme_competition_product=True,
            direct_production_required=True,
            company_cert_status="valid",
            eligibility_status="eligible",
            candidate_action="none",
            item_eligibility_required=True
        )
    )
    ctx = execute_rule_engine(gw)
    assert "품목별 중기경쟁제품·직접생산확인 추가 검토" in ctx.local_purchase_support_tools

def test_local_purchase_support_mapping_empty():
    gw = get_base_gateway_response()
    # No matching conditions
    ctx = execute_rule_engine(gw, {})
    assert ctx.local_purchase_support_review_required is False
    assert len(ctx.local_purchase_support_tools) == 0
