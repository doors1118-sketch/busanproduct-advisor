import pytest
from app.gateway.models.context import GatewayResponse, SourceContext, RouteContext, ProcedureContext, ItemEligibilityResult, GatewayMetadata, CompanyCandidateContext, CompanyCandidate, EnrichmentData
from app.rule_engine.decision_context import DecisionContext
from app.answer_builder.builder import build_answer

def get_base_gateway_response() -> GatewayResponse:
    return GatewayResponse(
        request_id="test-1",
        source_context=SourceContext(sources=[], buyer_type_confidence="high", required_slots_missing=[], assumed_buyer_type=None, assumption_reason=None),
        route_context=RouteContext(base_jurisdiction="local_contract", overlay_applied=False, overlay_scope=None, overlay_sources=[], dual_routing=False),
        procedure_context=ProcedureContext(sources=[], filter_applied=False, usage="answer_builder_procedure_section_only", judgment_eligible=False),
        item_eligibility_result=ItemEligibilityResult(resolver_status="not_triggered", unavailable_reason=None, context=None),
        metadata=GatewayMetadata(total_sources_matched=0, procedure_sources_matched=0, overlay_applied=False, item_eligibility_resolver_status="not_triggered", item_eligibility_trigger_grade=None, company_candidates_found=0, enrichment_applied=False, enrichment_scope=None),
        company_candidate_context=None
    )

def test_answer_builder_safe_outcome():
    gw = get_base_gateway_response()
    dc = DecisionContext(review_outcome="review_candidate")
    
    out = build_answer(gw, dc)
    assert out.forbidden_phrase_scan_passed is True
    assert out.fallback_applied is False
    assert "우선 검토 후보로 분류" in out.summary_section.content
    
    assert out.local_purchase_legal_review_section is not None
    assert "지역제한" in out.rendered_markdown
    assert "계약경로" in out.rendered_markdown
    assert "금액 기준 확인" in out.rendered_markdown

def test_answer_builder_ambiguous_creates_item_section():
    gw = get_base_gateway_response()
    dc = DecisionContext(review_outcome="manual_review_required", item_eligibility_status="ambiguous")
    
    out = build_answer(gw, dc)
    assert out.item_eligibility_section is not None
    assert "세부품명 확정이 불가합니다" in out.item_eligibility_section.content

def test_answer_builder_silent_adds_bullet():
    gw = get_base_gateway_response()
    dc = DecisionContext(review_outcome="review_candidate", item_eligibility_grade="silent")
    
    out = build_answer(gw, dc)
    assert len(out.summary_section.bullets) == 1
    assert "해당 품목이 중소기업자간 경쟁제품으로 특정되면" in out.summary_section.bullets[0]
    assert out.item_eligibility_section is None

def test_answer_builder_forbidden_phrase_fallback():
    gw = get_base_gateway_response()
    gw.company_candidate_context = CompanyCandidateContext(
        candidates=[
                CompanyCandidate(
                    company_id="hash1",
                    company_name_masked="계약 가능합니다", # 악의적인 데이터 주입
                    location="서울",
                    business_type=None,
                    contract_count=None,
                    contract_amount=None,
                    enrichment_data=None
                )      ],
        enrichment_applied=False,
        enrichment_scope=None,
        total_found=1
    )
    dc = DecisionContext(review_outcome="review_candidate")
    
    out = build_answer(gw, dc)
    assert out.forbidden_phrase_scan_passed is False
    assert out.fallback_applied is True
    assert "계약 가능합니다" in out.blocked_phrases_found
    
    # Fallback applied check
    assert "내부 검토 로직에 따라" in out.summary_section.content
    assert out.candidate_table_section is None
    assert out.local_purchase_legal_review_section is None
    assert "계약 가능합니다" not in out.rendered_markdown
