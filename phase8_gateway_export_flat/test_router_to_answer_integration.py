"""
Phase 10.3: Chatbot Runtime Pipeline Integration Test v0.1

사용자 질문이 챗봇 런타임 파이프라인을 통해 최소한의 응답 객체까지
정상적으로 이어지는지 검증하는 end-to-end skeleton 테스트.

User Query
→ GeminiIntentRouter.parse_gemini_response(mock)
→ DeterministicIntentValidator
→ RouterResult
→ AnswerTypeRouter.route_answer
→ AnswerBuilderOutput
→ forbidden phrase scan

실제 Gemini API, Company API, DB Source는 호출하지 않는다.
"""
import json
from app.router.gemini_intent_router import GeminiIntentRouter
from app.answer_builder.answer_type_router import route_answer, FORBIDDEN_PHRASES


def run_pipeline(query: str, mock_json: dict):
    router = GeminiIntentRouter()
    router_result = router.parse_gemini_response(query, json.dumps(mock_json, ensure_ascii=False))
    answer = route_answer(router_result)
    return router_result, answer


def _assert_no_forbidden(answer):
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in answer.rendered_markdown, f"Forbidden phrase '{phrase}' found"
    assert answer.forbidden_phrase_scan_passed is True


def _assert_no_fake_conclusion(md: str):
    """source gap 항목이 확정값처럼 출력되지 않는지 확인."""
    bad = ["적용할 수 있습니다", "기준은 확정", "가점은 ", "점입니다"]
    for b in bad:
        assert b not in md, f"Fake conclusion '{b}' found in markdown"


def _assert_routing_decision_not_empty(rr):
    assert rr.routing_decision != "", "routing_decision is empty"


# ────────────────────────────────────────────────────
# 1. legal_explanation_flow
# ────────────────────────────────────────────────────

def test_flow_legal_explanation():
    query = "수의계약에서 1인 견적과 2인 견적 차이가 뭐야?"
    mock = {"primary_intent": "legal_explanation", "confidence": 0.9, "slots": {"legal_topic": "수의계약"}}
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "legal_explanation_flow"
    assert rr.legal_explanation_only is True
    assert rr.candidate_lookup_required is False

    assert "법령·제도 설명" in ans.rendered_markdown
    assert "업체 후보 조회" not in ans.rendered_markdown
    assert ans.local_purchase_support_review_section is None
    assert ans.candidate_table_section is None
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 2. contract_review_flow
# ────────────────────────────────────────────────────

def test_flow_contract_review():
    query = "부산항만공사가 8천만원 LED조명을 구매하려고 한다. 어떻게 해야 해?"
    mock = {
        "primary_intent": "contract_review", "confidence": 0.9,
        "slots": {"buyer_name": "부산항만공사", "contract_object": "goods", "item_name": "LED조명", "amount": 80000000}
    }
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "contract_review_flow"
    assert "local_purchase_support" in rr.secondary_intents
    assert rr.legal_explanation_only is False
    assert rr.candidate_lookup_required is False

    assert "계약 검토 요약" in ans.rendered_markdown
    assert "지역업체 구매지원 제도 검토" in ans.rendered_markdown
    assert ans.local_purchase_support_review_section is not None
    assert "확인 필요" in ans.rendered_markdown
    assert "최신 법령 원문" in ans.rendered_markdown
    _assert_no_fake_conclusion(ans.rendered_markdown)
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 3. local_purchase_support_flow
# ────────────────────────────────────────────────────

def test_flow_local_purchase_support():
    query = "지역업체를 활용해서 물품을 구매하려면 어떤 제도를 검토해야 해?"
    mock = {
        "primary_intent": "local_purchase_support", "confidence": 0.9,
        "slots": {"contract_object": "goods", "local_supplier_intent": True}
    }
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "local_purchase_support_flow"
    assert rr.slots.local_supplier_intent is True

    assert "지역업체 구매지원 제도 검토" in ans.rendered_markdown
    assert ans.local_purchase_support_review_section is not None
    assert "적용 요건 확인" in ans.rendered_markdown
    _assert_no_fake_conclusion(ans.rendered_markdown)
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 4. candidate_search_flow
# ────────────────────────────────────────────────────

def test_flow_candidate_search():
    query = "CCTV 부산업체 추천해줘"
    mock = {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV", "location": "부산"}}
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "candidate_search_flow"
    assert rr.candidate_lookup_required is True
    assert rr.slots.local_supplier_intent is True
    assert rr.slots.candidate_lookup_requested is True

    assert "업체 후보 조회 조건" in ans.rendered_markdown
    assert "CCTV" in ans.rendered_markdown
    assert "부산" in ans.rendered_markdown
    assert "API 연동" in ans.rendered_markdown
    assert "조회합니다" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 5. item_eligibility_flow
# ────────────────────────────────────────────────────

def test_flow_item_eligibility():
    query = "LED조명이 중기경쟁제품인지 확인해줘"
    mock = {"primary_intent": "item_eligibility", "confidence": 0.9, "slots": {"item_name": "LED조명"}}
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "item_eligibility_flow"
    assert rr.slots.item_eligibility_requested is True

    assert "품목 자격 검토" in ans.rendered_markdown
    assert ans.item_eligibility_section is not None
    assert "업체 후보 조회" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 6. procurement_route_review_flow
# ────────────────────────────────────────────────────

def test_flow_procurement_route_review():
    query = "MAS랑 제3자단가계약 차이가 뭐야?"
    mock = {"primary_intent": "legal_explanation", "confidence": 0.9, "slots": {"legal_topic": "MAS와 제3자단가계약"}}
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "legal_explanation_flow"
    assert "procurement_route_review" in rr.secondary_intents
    assert rr.legal_explanation_only is True
    assert rr.candidate_lookup_required is False

    assert "법령·제도 설명" in ans.rendered_markdown
    assert "조달경로" in ans.rendered_markdown
    assert "업체 후보 조회" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 7. mixed_flow
# ────────────────────────────────────────────────────

def test_flow_mixed():
    query = "MAS에서 부산업체 제품 살 수 있나?"
    mock = {
        "primary_intent": "mixed", "confidence": 0.9,
        "secondary_intents": ["procurement_route_review", "local_purchase_support"],
        "slots": {"procurement_route": "mas", "local_supplier_intent": True}
    }
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "mixed_flow"
    assert "procurement_route_review" in rr.secondary_intents
    assert "local_purchase_support" in rr.secondary_intents
    assert rr.candidate_lookup_required is False
    assert "item_name" in rr.clarification_needed

    assert "복합 검토 요약" in ans.rendered_markdown
    assert "조달경로 검토" in ans.rendered_markdown
    assert "지역업체 구매지원 제도 검토" in ans.rendered_markdown
    assert "추가 확인 필요" in ans.rendered_markdown
    assert ans.route_review_section is not None
    assert ans.local_purchase_support_review_section is not None
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 8. clarification_required
# ────────────────────────────────────────────────────

def test_flow_clarification():
    query = "이거 해도 돼?"
    mock = {"primary_intent": "mixed", "confidence": 0.4, "slots": {}}
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "clarification_required"
    assert "의도 불분명" in rr.clarification_needed

    assert "추가 정보 요청" in ans.rendered_markdown
    assert "업체 후보 조회" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 9. out_of_scope
# ────────────────────────────────────────────────────

def test_flow_out_of_scope():
    query = "오늘 점심 뭐 먹지?"
    mock = {"primary_intent": "out_of_scope", "confidence": 0.95, "slots": {}}
    rr, ans = run_pipeline(query, mock)

    _assert_routing_decision_not_empty(rr)
    assert rr.routing_decision == "out_of_scope"

    assert "지원 범위 밖" in ans.rendered_markdown
    assert "업체 후보 조회" not in ans.rendered_markdown
    assert ans.local_purchase_support_review_section is None
    assert ans.candidate_table_section is None
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 10. 전체 금지 표현 일괄 sweep
# ────────────────────────────────────────────────────

def test_all_flows_forbidden_sweep():
    """모든 대표 flow에서 금지 표현이 없어야 한다."""
    cases = [
        ("수의계약이 뭐야?", {"primary_intent": "legal_explanation", "confidence": 0.9, "slots": {}}),
        ("LED조명 8천만원 구매", {"primary_intent": "contract_review", "confidence": 0.9, "slots": {"amount": 80000000, "item_name": "LED조명"}}),
        ("CCTV 추천해줘", {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV"}}),
        ("MAS에서 부산업체", {"primary_intent": "mixed", "confidence": 0.9, "slots": {"procurement_route": "mas"}}),
        ("오늘 점심 뭐 먹지?", {"primary_intent": "out_of_scope", "confidence": 0.95, "slots": {}}),
    ]
    for query, mock in cases:
        _, ans = run_pipeline(query, mock)
        _assert_no_forbidden(ans)
