"""
Chatbot Runtime Orchestrator Tests (Phase 10.4 + Phase 8.3 Safety Patch)

모든 테스트는 mock 기반. 실제 API 호출 없음.
"""
from app.runtime.chatbot_orchestrator import run_chatbot_runtime, ChatbotRuntimeOrchestrator, FORBIDDEN_PHRASES
from app.runtime.runtime_schema import ChatbotRuntimeRequest
from app.runtime.company_api_adapter import CompanyAPIAdapter, CompanyCandidateResult, CompanyCandidateRow


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
# 기본 flow 테스트
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
    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.skipped is True
    _assert_clean(resp)
    _assert_stages(resp)


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
    assert resp.answer_output.local_purchase_support_review_section is not None
    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.skipped is True
    _assert_clean(resp)
    _assert_stages(resp)


# ────────────────────────────────────────────────────
# Company API Adapter 통합 테스트
# ────────────────────────────────────────────────────

def test_runtime_candidate_search_with_company_api():
    resp = _run(
        "CCTV 부산업체 추천해줘",
        {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV", "location": "부산"}}
    )
    assert resp.runtime_status == "success"
    assert resp.router_result.candidate_lookup_required is True

    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.status == "success"

    assert resp.answer_output.candidate_table_section is not None
    assert len(resp.answer_output.candidate_table_section.rows) > 0
    assert "검토 후보" in resp.answer_output.candidate_table_section.description

    # 후보표 row에 상태 표시
    assert "검토 후보" in resp.answer_output.rendered_markdown
    assert "적격 확인 필요" in resp.answer_output.rendered_markdown
    assert "가나다***" in resp.answer_output.rendered_markdown
    assert "제조업" in resp.answer_output.rendered_markdown

    _assert_clean(resp)
    _assert_stages(resp)


def test_runtime_candidate_search_empty_result(monkeypatch):
    """Company API가 빈 결과를 반환하면 candidate_search_flow placeholder만 나옴."""
    def _empty_resolve(self, router_result):
        return CompanyCandidateResult(
            status="empty", total_found=0, search_query="품목: 존재하지않는품목"
        )

    monkeypatch.setattr(CompanyAPIAdapter, "resolve", _empty_resolve)

    resp = _run(
        "존재하지않는품목 추천해줘",
        {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "존재하지않는품목", "location": "부산"}}
    )
    assert resp.runtime_status == "success"
    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.status == "empty"
    assert resp.answer_output.candidate_table_section is None
    assert "API 연동" in resp.answer_output.rendered_markdown
    _assert_clean(resp)


def test_runtime_candidate_search_api_failed(monkeypatch):
    """Company API가 실패하면 degraded + placeholder."""
    def _fail_resolve(self, router_result):
        return CompanyCandidateResult(
            status="failed", error="Connection timeout", search_query="품목: CCTV"
        )

    monkeypatch.setattr(CompanyAPIAdapter, "resolve", _fail_resolve)

    resp = _run(
        "CCTV 추천해줘",
        {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV", "location": "부산"}}
    )
    assert resp.runtime_status == "degraded"
    cs = _get_stage(resp, "company_candidate_resolver")
    assert cs is not None and cs.status == "failed"
    assert "Connection timeout" in cs.reason
    # 답변 자체는 placeholder로 정상 생성
    assert "API 연동" in resp.answer_output.rendered_markdown
    _assert_clean(resp)


# ────────────────────────────────────────────────────
# Forbidden phrase re-scan after candidate table
# ────────────────────────────────────────────────────

def test_runtime_forbidden_rescan_after_candidate_table(monkeypatch):
    """후보표에 금지 표현이 포함되면 re-scan이 잡아야 한다."""
    def _poisoned_resolve(self, router_result):
        return CompanyCandidateResult(
            status="success",
            candidates=[
                CompanyCandidateRow(
                    company_id="bad_001",
                    company_name_masked="수의계약 가능합니다***",  # 금지 표현이 이름에 포함
                    location="부산",
                    business_type="제조업",
                    main_products=["CCTV"],
                    display_status="검토 후보",
                    legal_eligibility_status="확인 필요"
                )
            ],
            total_found=1,
            search_query="품목: CCTV"
        )

    monkeypatch.setattr(CompanyAPIAdapter, "resolve", _poisoned_resolve)

    resp = _run(
        "CCTV 추천해줘",
        {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV", "location": "부산"}}
    )

    # re-scan이 금지 표현을 감지해야 함
    assert resp.answer_output.forbidden_phrase_scan_passed is False
    assert len(resp.answer_output.blocked_phrases_found) > 0
    assert resp.answer_output.fallback_applied is True
    assert resp.runtime_status == "degraded"


# ────────────────────────────────────────────────────
# Location 필터 검증
# ────────────────────────────────────────────────────

def test_runtime_candidate_search_location_tracked():
    """검색 조건에 location이 포함되는지 확인."""
    resp = _run(
        "CCTV 부산업체 추천해줘",
        {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV", "location": "부산"}}
    )
    assert "부산" in resp.answer_output.rendered_markdown
    _assert_clean(resp)


# ────────────────────────────────────────────────────
# 기타 flow
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
    _assert_clean(resp)
    _assert_stages(resp)


def test_runtime_low_confidence():
    resp = _run("이거 해도 돼?", {"primary_intent": "mixed", "confidence": 0.4, "slots": {}})
    assert resp.runtime_status == "success"
    assert resp.router_result.routing_decision == "clarification_required"
    _assert_clean(resp)
    _assert_stages(resp)


def test_runtime_out_of_scope():
    resp = _run("오늘 점심 뭐 먹지?", {"primary_intent": "out_of_scope", "confidence": 0.95, "slots": {}})
    assert resp.runtime_status == "success"
    assert "지원 범위 밖" in resp.answer_output.rendered_markdown
    _assert_clean(resp)
    _assert_stages(resp)


# ────────────────────────────────────────────────────
# 금지 표현 sweep
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
# Fallback 안전성
# ────────────────────────────────────────────────────

def test_runtime_no_mock_response_safe_fallback():
    req = ChatbotRuntimeRequest(user_query="아무거나", mock_gemini_response=None)
    resp = run_chatbot_runtime(req)
    assert resp.runtime_status == "success"
    assert resp.router_result.routing_decision != ""
    _assert_clean(resp)


def test_runtime_router_exception_fallback(monkeypatch):
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
