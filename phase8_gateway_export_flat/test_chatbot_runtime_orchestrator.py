"""
Chatbot Runtime Orchestrator Tests (Phase 10.4 + Phase 8.3)

사용자 질문 → Intent Router → Gateway(stub) → Rule Engine(stub)
→ Company API Adapter → Answer Type Router → Runtime Response

모든 테스트는 mock 기반. 실제 API 호출 없음.
"""
from app.runtime.chatbot_orchestrator import run_chatbot_runtime
from app.runtime.runtime_schema import ChatbotRuntimeRequest
from app.answer_builder.answer_type_router import FORBIDDEN_PHRASES


def _run(query: str, mock: dict):
    req = ChatbotRuntimeRequest(user_query=query, mock_gemini_response=mock)
    return run_chatbot_runtime(req)


def _assert_clean(resp):
    """금지 표현 없음 + scan 통과."""
    assert resp.answer_output.forbidden_phrase_scan_passed is True
    assert resp.answer_output.blocked_phrases_found == []
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in resp.answer_output.rendered_markdown


def _assert_stages(resp):
    """runtime_stages 기본 검증."""
    assert len(resp.runtime_stages) >= 2
    assert resp.router_result.routing_decision != ""
    gw = next((s for s in resp.runtime_stages if s.stage_name == "gateway_context"), None)
    re = next((s for s in resp.runtime_stages if s.stage_name == "rule_engine"), None)
    assert gw is not None and gw.skipped is True
    assert re is not None and re.skipped is True


def _get_stage(resp, name):
    return next((s for s in resp.runtime_stages if s.stage_name == name), None)


# ────────────────────────────────────────────────────
# 8.1 일반 법령 질의
# ────────────────────────────────────────────────────

def test_runtime_legal_explanation():
    resp = _run(
        "수의계약에서 1인 견적과 2인 견적 차이가 뭐야?",
        {"primary_intent": "legal_explanation", "confidence": 0.9, "slots": {"legal_topic": "수의계약"}}
    )
    assert resp.runtime_status == "success"
    assert resp.router_result.primary_intent == "legal_explanation"
    assert "법령·제도 설명" in resp.answer_output.rendered_markdown
    assert resp.answer_output.candidate_table_section is None

    # company resolver는 skipped
    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.skipped is True

    _assert_clean(resp)
    _assert_stages(resp)


# ────────────────────────────────────────────────────
# 8.2 구체 구매 검토
# ────────────────────────────────────────────────────

def test_runtime_contract_review():
    resp = _run(
        "부산항만공사가 8천만원 LED조명을 구매하려고 한다. 어떻게 해야 해?",
        {
            "primary_intent": "contract_review", "confidence": 0.9,
            "slots": {"buyer_name": "부산항만공사", "contract_object": "goods", "item_name": "LED조명", "amount": 80000000}
        }
    )
    assert resp.runtime_status == "success"
    assert "계약 검토 요약" in resp.answer_output.rendered_markdown
    assert "지역업체 구매지원 제도 검토" in resp.answer_output.rendered_markdown
    assert resp.answer_output.local_purchase_support_review_section is not None

    # candidate_lookup_required=False이므로 company resolver skipped
    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.skipped is True

    _assert_clean(resp)
    _assert_stages(resp)


# ────────────────────────────────────────────────────
# 8.3 후보조회 → Company API Adapter 동작
# ────────────────────────────────────────────────────

def test_runtime_candidate_search_with_company_api():
    resp = _run(
        "CCTV 부산업체 추천해줘",
        {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV", "location": "부산"}}
    )
    assert resp.runtime_status == "success"
    assert resp.router_result.candidate_lookup_required is True

    # company resolver가 success
    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.status == "success"

    # 후보표가 생성됨
    assert resp.answer_output.candidate_table_section is not None
    assert len(resp.answer_output.candidate_table_section.rows) > 0
    assert "검토 후보" in resp.answer_output.candidate_table_section.description
    assert "계약 가능" not in resp.answer_output.candidate_table_section.description

    # rendered_markdown에 후보표 포함
    assert "검토 후보 업체" in resp.answer_output.rendered_markdown
    assert "가나다***" in resp.answer_output.rendered_markdown

    _assert_clean(resp)
    _assert_stages(resp)


# ────────────────────────────────────────────────────
# 8.4 mixed → company resolver skipped
# ────────────────────────────────────────────────────

def test_runtime_mixed():
    resp = _run(
        "MAS에서 부산업체 제품 살 수 있나?",
        {
            "primary_intent": "mixed", "confidence": 0.9,
            "secondary_intents": ["procurement_route_review", "local_purchase_support"],
            "slots": {"procurement_route": "mas", "local_supplier_intent": True}
        }
    )
    assert resp.runtime_status == "success"
    assert resp.router_result.candidate_lookup_required is False

    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.skipped is True

    assert "조달경로 검토" in resp.answer_output.rendered_markdown
    assert "지역업체 구매지원 제도 검토" in resp.answer_output.rendered_markdown
    _assert_clean(resp)
    _assert_stages(resp)


# ────────────────────────────────────────────────────
# 8.5 low confidence
# ────────────────────────────────────────────────────

def test_runtime_low_confidence():
    resp = _run("이거 해도 돼?", {"primary_intent": "mixed", "confidence": 0.4, "slots": {}})
    assert resp.runtime_status == "success"
    assert resp.router_result.routing_decision == "clarification_required"
    assert "추가 정보 요청" in resp.answer_output.rendered_markdown
    _assert_clean(resp)
    _assert_stages(resp)


# ────────────────────────────────────────────────────
# 8.6 out_of_scope
# ────────────────────────────────────────────────────

def test_runtime_out_of_scope():
    resp = _run("오늘 점심 뭐 먹지?", {"primary_intent": "out_of_scope", "confidence": 0.95, "slots": {}})
    assert resp.runtime_status == "success"
    assert "지원 범위 밖" in resp.answer_output.rendered_markdown
    _assert_clean(resp)
    _assert_stages(resp)


# ────────────────────────────────────────────────────
# 9. 금지 표현 sweep
# ────────────────────────────────────────────────────

def test_runtime_forbidden_sweep():
    cases = [
        ("수의계약이 뭐야?", {"primary_intent": "legal_explanation", "confidence": 0.9, "slots": {}}),
        ("LED조명 구매", {"primary_intent": "contract_review", "confidence": 0.9, "slots": {"amount": 80000000, "item_name": "LED조명"}}),
        ("CCTV 추천", {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV"}}),
        ("MAS 부산업체", {"primary_intent": "mixed", "confidence": 0.9, "slots": {"procurement_route": "mas"}}),
        ("점심 뭐 먹지?", {"primary_intent": "out_of_scope", "confidence": 0.95, "slots": {}}),
    ]
    for query, mock in cases:
        resp = _run(query, mock)
        _assert_clean(resp)


# ────────────────────────────────────────────────────
# 10. Fallback 안전성
# ────────────────────────────────────────────────────

def test_runtime_no_mock_response_safe_fallback():
    """mock=None이면 내부 synthetic out_of_scope로 안전 처리."""
    req = ChatbotRuntimeRequest(user_query="아무거나", mock_gemini_response=None)
    resp = run_chatbot_runtime(req)
    assert resp.runtime_status == "success"
    assert resp.router_result.routing_decision != ""
    _assert_clean(resp)


def test_runtime_router_exception_fallback(monkeypatch):
    """Router에서 예외가 발생하면 fail-closed fallback."""
    def _raise(*args, **kwargs):
        raise RuntimeError("Simulated Gemini failure")

    monkeypatch.setattr(
        "app.runtime.chatbot_orchestrator.GeminiIntentRouter.parse_gemini_response",
        _raise
    )
    req = ChatbotRuntimeRequest(
        user_query="테스트", mock_gemini_response={"primary_intent": "legal_explanation", "slots": {}}
    )
    resp = run_chatbot_runtime(req)
    assert resp.runtime_status == "failed"
    assert resp.fallback_applied is True
    assert "intent_router" in resp.errors[0]
    _assert_clean(resp)
