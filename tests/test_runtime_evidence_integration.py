"""
Phase 10.5: Runtime Evidence Integration Tests

Runtime Orchestrator + Evidence Builder 통합 테스트.
"""
from app.runtime.chatbot_orchestrator import run_chatbot_runtime, FORBIDDEN_PHRASES
from app.runtime.runtime_schema import ChatbotRuntimeRequest
from app.answer_builder.evidence_answer_builder import FORBIDDEN_NUMERIC_HINTS


def _get_stage(resp, name):
    return next((s for s in resp.runtime_stages if s.stage_name == name), None)


def test_evidence_mode_contract_review():
    """evidence mode ON + contract_review → evidence_context stage success."""
    req = ChatbotRuntimeRequest(
        user_query="부산항만공사가 8천만원 LED조명을 구매하려고 한다. 어떻게 해야 해?",
        mock_gemini_response={
            "primary_intent": "contract_review", "confidence": 0.9,
            "slots": {"buyer_name": "부산항만공사", "contract_object": "goods", "item_name": "LED조명", "amount": 80000000}
        },
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True}
    )
    resp = run_chatbot_runtime(req)

    assert resp.runtime_status == "success"

    # evidence_context stage 존재
    ec = _get_stage(resp, "evidence_context")
    assert ec is not None and ec.status == "success"

    # evidence section이 markdown에 포함
    assert "근거 기반 검토 상태" in resp.answer_output.rendered_markdown

    # 금지 표현 없음
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in resp.answer_output.rendered_markdown


def test_evidence_mode_no_forbidden_numerics():
    """unresolved 수치가 출력되지 않아야 함."""
    req = ChatbotRuntimeRequest(
        user_query="부산항만공사가 LED조명을 구매하려면?",
        mock_gemini_response={
            "primary_intent": "contract_review", "confidence": 0.9,
            "slots": {"buyer_name": "부산항만공사", "contract_object": "goods", "item_name": "LED조명"}
        },
        runtime_options={"use_evidence_builder": True}
    )
    resp = run_chatbot_runtime(req)

    for hint in FORBIDDEN_NUMERIC_HINTS:
        assert hint not in resp.answer_output.rendered_markdown


def test_evidence_mode_source_gap_shown():
    """partial_mapped rule이 있으면 확인 필요 표시."""
    req = ChatbotRuntimeRequest(
        user_query="수의계약으로 물품 구매하려면?",
        mock_gemini_response={
            "primary_intent": "contract_review", "confidence": 0.9,
            "slots": {"contract_object": "goods", "item_name": "물품"}
        },
        runtime_options={"use_evidence_builder": True}
    )
    resp = run_chatbot_runtime(req)

    md = resp.answer_output.rendered_markdown
    # partial_mapped / pending rule이 있으면 gap 관련 문구 확인
    has_gap_phrase = ("미매핑" in md or "확인 필요" in md or "직접 근거" in md)
    assert has_gap_phrase


def test_evidence_mode_off_skips_stage():
    """evidence mode OFF → evidence_context stage는 skipped."""
    req = ChatbotRuntimeRequest(
        user_query="수의계약이 뭐야?",
        mock_gemini_response={
            "primary_intent": "legal_explanation", "confidence": 0.9,
            "slots": {"legal_topic": "수의계약"}
        },
        runtime_options={"use_evidence_builder": False}
    )
    resp = run_chatbot_runtime(req)

    ec = _get_stage(resp, "evidence_context")
    assert ec is not None and ec.skipped is True

    # evidence section이 없어야 함
    assert "근거 기반 검토 상태" not in resp.answer_output.rendered_markdown


def test_evidence_default_off():
    """기본값은 evidence OFF."""
    req = ChatbotRuntimeRequest(
        user_query="수의계약이 뭐야?",
        mock_gemini_response={
            "primary_intent": "legal_explanation", "confidence": 0.9,
            "slots": {"legal_topic": "수의계약"}
        }
    )
    resp = run_chatbot_runtime(req)

    ec = _get_stage(resp, "evidence_context")
    assert ec is not None and ec.skipped is True


def test_evidence_mode_candidate_search():
    """candidate_search + evidence → company_api_only label."""
    req = ChatbotRuntimeRequest(
        user_query="CCTV 부산업체 추천해줘",
        mock_gemini_response={
            "primary_intent": "candidate_search", "confidence": 0.9,
            "slots": {"item_name": "CCTV", "location": "부산"}
        },
        runtime_options={"use_evidence_builder": True, "use_mock_company_api": True}
    )
    resp = run_chatbot_runtime(req)

    assert resp.runtime_status == "success"
    assert "근거 기반 검토 상태" in resp.answer_output.rendered_markdown
    assert resp.answer_output.candidate_table_section is not None

    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in resp.answer_output.rendered_markdown


def test_evidence_mode_existing_tests_unbroken():
    """evidence OFF인 기존 flow가 깨지지 않아야 함."""
    cases = [
        ("법령", {"primary_intent": "legal_explanation", "confidence": 0.9, "slots": {}}),
        ("구매", {"primary_intent": "contract_review", "confidence": 0.9, "slots": {"item_name": "LED"}}),
        ("범위밖", {"primary_intent": "out_of_scope", "confidence": 0.95, "slots": {}}),
    ]
    for query, mock in cases:
        req = ChatbotRuntimeRequest(user_query=query, mock_gemini_response=mock)
        resp = run_chatbot_runtime(req)
        assert resp.runtime_status == "success"
        assert resp.answer_output.forbidden_phrase_scan_passed is True
