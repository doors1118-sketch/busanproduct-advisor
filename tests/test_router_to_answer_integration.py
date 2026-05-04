"""
Phase 10.3: Router-to-Answer Integration Test

사용자 질문 → GeminiIntentRouter → DeterministicIntentValidator → RouterResult → AnswerTypeRouter → AnswerBuilderOutput
전체 파이프라인을 mock Gemini 응답 기반으로 통합 검증한다.

이 테스트는 실제 Gemini API를 호출하지 않는다.
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


# ────────────────────────────────────────────────────
# 5.1 일반 법령 설명 질의
# ────────────────────────────────────────────────────

def test_5_1_legal_explanation():
    query = "수의계약에서 1인 견적과 2인 견적 차이가 뭐야?"
    mock = {
        "primary_intent": "legal_explanation",
        "confidence": 0.9,
        "slots": {"legal_topic": "수의계약"}
    }
    rr, ans = run_pipeline(query, mock)

    # Router
    assert rr.primary_intent == "legal_explanation"
    assert rr.routing_decision == "legal_explanation_flow"
    assert rr.legal_explanation_only is True
    assert rr.candidate_lookup_required is False

    # Answer
    assert "법령·제도 설명" in ans.rendered_markdown
    assert "업체 후보 조회" not in ans.rendered_markdown
    assert ans.local_purchase_support_review_section is None
    assert ans.candidate_table_section is None
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 5.2 지역제한 개념 설명 질의
# ────────────────────────────────────────────────────

def test_5_2_regional_restriction_explanation():
    query = "지역제한 입찰이 뭐야?"
    mock = {
        "primary_intent": "legal_explanation",
        "confidence": 0.9,
        "slots": {"legal_topic": "지역제한 입찰"}
    }
    rr, ans = run_pipeline(query, mock)

    # Router
    assert rr.primary_intent == "legal_explanation"
    assert rr.legal_explanation_only is True
    assert rr.candidate_lookup_required is False
    assert "item_name" not in rr.clarification_needed

    # Answer: 법령 설명형, 구매지원 제도 검토 섹션 자동 출력 금지
    assert "법령·제도 설명" in ans.rendered_markdown
    assert ans.local_purchase_support_review_section is None
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 5.3 구체적 구매 검토 질의
# ────────────────────────────────────────────────────

def test_5_3_concrete_contract_review():
    query = "부산항만공사가 8천만원 LED조명을 구매하려고 한다. 어떻게 해야 해?"
    mock = {
        "primary_intent": "contract_review",
        "confidence": 0.9,
        "slots": {
            "buyer_name": "부산항만공사",
            "contract_object": "goods",
            "item_name": "LED조명",
            "amount": 80000000
        }
    }
    rr, ans = run_pipeline(query, mock)

    # Router
    assert rr.primary_intent == "contract_review"
    assert rr.routing_decision == "contract_review_flow"
    assert "local_purchase_support" in rr.secondary_intents
    assert rr.legal_explanation_only is False
    assert rr.candidate_lookup_required is False

    # Answer
    assert "계약 검토 요약" in ans.rendered_markdown
    assert "지역업체 구매지원 제도 검토" in ans.rendered_markdown
    assert ans.local_purchase_support_review_section is not None
    assert "확인 필요" in ans.rendered_markdown
    assert "최신 법령 원문" in ans.rendered_markdown

    # Source gap: 확정값 없음
    assert "적용할 수 있습니다" not in ans.rendered_markdown
    assert "기준은 확정" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 5.4 후보업체 요청 질의
# ────────────────────────────────────────────────────

def test_5_4_candidate_search():
    query = "CCTV 부산업체 추천해줘"
    mock = {
        "primary_intent": "candidate_search",
        "confidence": 0.9,
        "slots": {
            "item_name": "CCTV",
            "location": "부산"
        }
    }
    rr, ans = run_pipeline(query, mock)

    # Router
    assert rr.primary_intent == "candidate_search"
    assert rr.routing_decision == "candidate_search_flow"
    assert "local_purchase_support" in rr.secondary_intents
    assert rr.slots.local_supplier_intent is True
    assert rr.slots.candidate_lookup_requested is True
    assert rr.candidate_lookup_required is True

    # Answer
    assert "업체 후보 조회 조건" in ans.rendered_markdown
    assert "CCTV" in ans.rendered_markdown
    assert "부산" in ans.rendered_markdown
    assert "API 연동" in ans.rendered_markdown
    assert "조회합니다" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 5.5 MAS + 지역업체 혼합 질의
# ────────────────────────────────────────────────────

def test_5_5_mas_mixed():
    query = "MAS에서 부산업체 제품 살 수 있나?"
    mock = {
        "primary_intent": "mixed",
        "confidence": 0.9,
        "secondary_intents": ["procurement_route_review", "local_purchase_support"],
        "slots": {
            "procurement_route": "mas",
            "local_supplier_intent": True
        }
    }
    rr, ans = run_pipeline(query, mock)

    # Router
    assert rr.primary_intent == "mixed"
    assert rr.routing_decision == "mixed_flow"
    assert "procurement_route_review" in rr.secondary_intents
    assert "local_purchase_support" in rr.secondary_intents
    assert rr.candidate_lookup_required is False
    assert "item_name" in rr.clarification_needed

    # Answer
    assert "복합 검토 요약" in ans.rendered_markdown
    assert "조달경로 검토" in ans.rendered_markdown
    assert "지역업체 구매지원 제도 검토" in ans.rendered_markdown
    assert "추가 확인 필요" in ans.rendered_markdown
    assert ans.route_review_section is not None
    assert ans.local_purchase_support_review_section is not None
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 5.6 품목 자격 질의
# ────────────────────────────────────────────────────

def test_5_6_item_eligibility():
    query = "LED조명이 중기경쟁제품인지 확인해줘"
    mock = {
        "primary_intent": "item_eligibility",
        "confidence": 0.9,
        "slots": {"item_name": "LED조명"}
    }
    rr, ans = run_pipeline(query, mock)

    # Router
    assert rr.primary_intent == "item_eligibility"
    assert rr.routing_decision == "item_eligibility_flow"
    assert rr.slots.item_eligibility_requested is True

    # Answer
    assert "품목 자격 검토" in ans.rendered_markdown
    assert ans.item_eligibility_section is not None
    assert "업체 후보 조회" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 5.7 조달경로 설명 질의
# ────────────────────────────────────────────────────

def test_5_7_route_explanation():
    query = "제3자단가계약이랑 MAS 차이가 뭐야?"
    mock = {
        "primary_intent": "legal_explanation",
        "confidence": 0.9,
        "slots": {"legal_topic": "제3자단가계약과 MAS"}
    }
    rr, ans = run_pipeline(query, mock)

    # Router
    assert rr.primary_intent == "legal_explanation"
    assert "procurement_route_review" in rr.secondary_intents
    assert rr.routing_decision == "legal_explanation_flow"
    assert rr.legal_explanation_only is True
    assert rr.candidate_lookup_required is False

    # Answer
    assert "법령·제도 설명" in ans.rendered_markdown
    assert "조달경로" in ans.rendered_markdown
    assert "업체 후보 조회" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 5.8 낮은 confidence fallback
# ────────────────────────────────────────────────────

def test_5_8_low_confidence_fallback():
    query = "이거 해도 돼?"
    mock = {
        "primary_intent": "mixed",
        "confidence": 0.4,
        "slots": {}
    }
    rr, ans = run_pipeline(query, mock)

    # Router
    assert rr.routing_decision == "clarification_required"
    assert "의도 불분명" in rr.clarification_needed

    # Answer
    assert "추가 정보 요청" in ans.rendered_markdown
    assert "업체 후보 조회" not in ans.rendered_markdown
    _assert_no_forbidden(ans)


# ────────────────────────────────────────────────────
# 6. 금지 표현 일괄 검증
# ────────────────────────────────────────────────────

def test_all_flows_no_forbidden():
    """모든 대표 flow의 최종 markdown에 금지 표현이 없어야 한다."""
    cases = [
        ("수의계약이 뭐야?", {"primary_intent": "legal_explanation", "confidence": 0.9, "slots": {}}),
        ("LED조명 8천만원 구매", {"primary_intent": "contract_review", "confidence": 0.9, "slots": {"amount": 80000000, "item_name": "LED조명"}}),
        ("CCTV 추천해줘", {"primary_intent": "candidate_search", "confidence": 0.9, "slots": {"item_name": "CCTV"}}),
        ("MAS에서 부산업체", {"primary_intent": "mixed", "confidence": 0.9, "slots": {"procurement_route": "mas"}}),
    ]
    for query, mock in cases:
        _, ans = run_pipeline(query, mock)
        _assert_no_forbidden(ans)
