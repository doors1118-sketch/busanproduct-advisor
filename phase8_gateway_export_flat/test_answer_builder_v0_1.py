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
    dc = DecisionContext(
        review_outcome="review_candidate",
        local_purchase_support_tools=[
            "지역의무공동도급 검토",
            "수의계약 활용 가능성 검토",
            "MAS·종합쇼핑몰 내 지역업체 후보 활용 검토"
        ]
    )
    
    out = build_answer(gw, dc)
    assert out.forbidden_phrase_scan_passed is True
    assert out.fallback_applied is False
    assert "우선 검토 후보로 분류" in out.summary_section.content
    
    assert out.local_purchase_support_review_section is not None
    assert "지역의무공동도급 검토" in out.rendered_markdown
    assert "수의계약 활용 가능성 검토" in out.rendered_markdown
    assert "MAS·종합쇼핑몰 내 지역업체 후보 활용 검토" in out.rendered_markdown

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
    assert out.local_purchase_support_review_section is None
    assert "계약 가능합니다" not in out.rendered_markdown
    assert "구매 가능합니다" not in out.rendered_markdown
    assert "수의계약 가능합니다" not in out.rendered_markdown
    assert "낙찰 가능합니다" not in out.rendered_markdown

def test_answer_builder_threshold_display():
    gw = get_base_gateway_response()
    dc = DecisionContext(review_outcome="review_candidate")
    
    from app.answer_builder.evidence_schema import EvidenceContext, RuleEvidenceStatus, EvidenceParameterStatus
    
    # Mock EvidenceContext with threshold
    ec = EvidenceContext(
        active_rule_ids=["R_DIRECT_GENERAL_SMALL_AMOUNT"],
        rule_statuses=[
            RuleEvidenceStatus(
                rule_id="R_DIRECT_GENERAL_SMALL_AMOUNT",
                display_name="소액수의계약",
                category="수의계약",
                source_chain_status="mapped_verified",
                display_level="source_verified",
                numeric_parameters=[EvidenceParameterStatus(parameter_ref="P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD", display_allowed=True)]
            )
        ],
        threshold_ref_used="P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD",
        threshold_value_used=50000000
    )
    
    from app.answer_builder.evidence_answer_builder import apply_evidence_to_answer
    out = build_answer(gw, dc)
    out = apply_evidence_to_answer(out, ec)
    
    # Check if threshold is displayed with LABEL mapping
    assert "적용 기준" in out.rendered_markdown
    assert "정책기업 수의계약 기준" in out.rendered_markdown
    assert "50,000,000원" in out.rendered_markdown
    
    # Should not be masked by FORBIDDEN_NUMERIC_HINTS
    assert "[수치 확인 필요]" not in out.rendered_markdown
    assert out.forbidden_phrase_scan_passed is True

def test_answer_builder_threshold_not_displayed_if_unresolved():
    gw = get_base_gateway_response()
    dc = DecisionContext(review_outcome="review_candidate")
    
    from app.answer_builder.evidence_schema import EvidenceContext, RuleEvidenceStatus, EvidenceParameterStatus
    
    # Mock EvidenceContext with unresolved parameter
    ec = EvidenceContext(
        active_rule_ids=["R_DIRECT_GENERAL_SMALL_AMOUNT"],
        rule_statuses=[
            RuleEvidenceStatus(
                rule_id="R_DIRECT_GENERAL_SMALL_AMOUNT",
                display_name="소액수의계약",
                category="수의계약",
                source_chain_status="mapped_verified",
                display_level="source_verified",
                numeric_parameters=[EvidenceParameterStatus(parameter_ref="P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD", display_allowed=False)]
            )
        ],
        threshold_ref_used="P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD",
        threshold_value_used=50000000
    )
    
    from app.answer_builder.evidence_answer_builder import apply_evidence_to_answer
    out = build_answer(gw, dc)
    out = apply_evidence_to_answer(out, ec)
    
    # Check if threshold is NOT displayed due to display_allowed=False
    assert "적용 기준" not in out.rendered_markdown
    assert "50,000,000원" not in out.rendered_markdown
    # 수치 기준 확인 필요 메시지 표시 여부
    assert "수치 기준은 최신 법령 원문 확인 필요" in out.rendered_markdown
    # 원문 렌더링이 차단되었는지 확인 (source_verified 이더라도 unresolved이면 <details> 차단됨)
    assert "<details>" not in out.rendered_markdown

def test_answer_builder_unknown_parameter_ref_hidden():
    gw = get_base_gateway_response()
    dc = DecisionContext(review_outcome="review_candidate")
    from app.answer_builder.evidence_schema import EvidenceContext, RuleEvidenceStatus, EvidenceParameterStatus
    
    ec = EvidenceContext(
        active_rule_ids=["R_DIRECT_GENERAL_SMALL_AMOUNT"],
        rule_statuses=[
            RuleEvidenceStatus(
                rule_id="R_DIRECT_GENERAL_SMALL_AMOUNT",
                display_name="소액수의계약",
                category="수의계약",
                source_chain_status="mapped_verified",
                display_level="source_verified",
                numeric_parameters=[EvidenceParameterStatus(parameter_ref="UNKNOWN_REF", display_allowed=True)]
            )
        ],
        threshold_ref_used="UNKNOWN_REF",
        threshold_value_used=50000000
    )
    
    from app.answer_builder.evidence_answer_builder import apply_evidence_to_answer
    out = build_answer(gw, dc)
    out = apply_evidence_to_answer(out, ec)
    
    # UNKNOWN_REF is not in PARAMETER_LABELS, so it should not be displayed
    assert "적용 기준" not in out.rendered_markdown
    assert "UNKNOWN_REF" not in out.rendered_markdown

def test_answer_builder_key_articles_load():
    gw = get_base_gateway_response()
    dc = DecisionContext(review_outcome="review_candidate")
    from app.answer_builder.evidence_schema import EvidenceContext, RuleEvidenceStatus, EvidenceParameterStatus
    
    # Create a temporary key_articles.json to test actual loading
    import os, json
    test_articles_path = os.path.join(os.path.dirname(__file__), "key_articles.json")
    long_text = "A" * 300
    with open(test_articles_path, "w", encoding="utf-8") as f:
        json.dump({"R_TEST_RULE": long_text}, f)
        
    try:
        ec = EvidenceContext(
            active_rule_ids=["R_TEST_RULE"],
            rule_statuses=[
                RuleEvidenceStatus(
                    rule_id="R_TEST_RULE",
                    display_name="테스트 룰",
                    category="테스트",
                    source_chain_status="mapped_verified",
                    display_level="source_verified",
                    numeric_parameters=[] # No numeric parameters, so display_allowed is True implicitly
                )
            ]
        )
        
        from phase8_gateway_export_flat.evidence_answer_builder import apply_evidence_to_answer
        out = build_answer(gw, dc)
        out = apply_evidence_to_answer(out, ec)
        
        # Ensure the article was loaded and truncated
        assert "관련 조문 발췌 보기" in out.rendered_markdown
        assert "A" * 200 in out.rendered_markdown
        assert "A" * 250 not in out.rendered_markdown
        assert "너무 긴 원문은 가독성을 위해 축약되었습니다" in out.rendered_markdown
    finally:
        if os.path.exists(test_articles_path):
            os.remove(test_articles_path)
