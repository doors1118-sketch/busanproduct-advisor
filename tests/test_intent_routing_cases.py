import json
from app.router.gemini_intent_router import GeminiIntentRouter

def test_case_8_1_general_legal():
    router = GeminiIntentRouter()
    query = "수의계약에서 1인 견적과 2인 견적 차이가 뭐야?"
    mock_json = {
        "primary_intent": "legal_explanation",
        "slots": {}
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))
    
    assert result.primary_intent == "legal_explanation"
    assert result.legal_explanation_only is True
    assert result.candidate_lookup_required is False
    assert "item_name" not in result.clarification_needed
    assert result.routing_decision != ""
    assert result.routing_decision == "legal_explanation_flow"

def test_case_8_2_regional_explanation():
    router = GeminiIntentRouter()
    query = "지역제한 입찰이 뭐야?"
    mock_json = {
        "primary_intent": "legal_explanation",
        "slots": {}
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))
    
    assert result.primary_intent == "legal_explanation"
    assert "local_purchase_support" in result.secondary_intents
    assert result.legal_explanation_only is True
    assert result.candidate_lookup_required is False
    assert "item_name" not in result.clarification_needed
    assert result.routing_decision == "legal_explanation_flow"

def test_case_8_3_specific_purchase():
    router = GeminiIntentRouter()
    query = "부산항만공사가 8천만원 LED조명을 구매하려고 한다. 어떻게 해야 해?"
    mock_json = {
        "primary_intent": "contract_review",
        "secondary_intents": ["local_purchase_support"],
        "slots": {
            "buyer_name": "부산항만공사",
            "contract_object": "goods",
            "item_name": "LED조명",
            "amount": 80000000
        }
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))
    
    assert result.primary_intent == "contract_review"
    assert "local_purchase_support" in result.secondary_intents
    assert result.legal_explanation_only is False
    assert result.candidate_lookup_required is False
    assert result.routing_decision == "contract_review_flow"

def test_case_8_4_candidate_search():
    router = GeminiIntentRouter()
    query = "CCTV 부산업체 추천해줘"
    mock_json = {
        "primary_intent": "candidate_search",
        "slots": {
            "item_name": "CCTV",
            "location": "부산"
        }
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))
    
    assert result.primary_intent == "candidate_search"
    assert "local_purchase_support" in result.secondary_intents
    assert result.candidate_lookup_required is True
    assert result.slots.item_name == "CCTV"
    assert result.slots.local_supplier_intent is True
    assert result.slots.candidate_lookup_requested is True
    assert result.slots.location == "부산"
    assert result.routing_decision == "candidate_search_flow"

def test_case_8_5_mas_mixed():
    router = GeminiIntentRouter()
    query = "MAS에서 부산업체 제품 살 수 있나?"
    mock_json = {
        "primary_intent": "mixed",
        "secondary_intents": ["procurement_route_review", "local_purchase_support"],
        "slots": {
            "procurement_route": "mas",
            "local_supplier_intent": True
        }
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))
    
    assert result.primary_intent == "mixed"
    assert "procurement_route_review" in result.secondary_intents
    assert "local_purchase_support" in result.secondary_intents
    assert result.candidate_lookup_required is False
    assert result.legal_explanation_only is False
    assert "item_name" in result.clarification_needed
    assert result.routing_decision == "mixed_flow"

def test_case_8_6_item_eligibility():
    router = GeminiIntentRouter()
    query = "LED조명이 중기경쟁제품인지 확인해줘"
    mock_json = {
        "primary_intent": "item_eligibility",
        "slots": {
            "item_name": "LED조명"
        }
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))
    
    assert result.primary_intent == "item_eligibility"
    assert result.slots.item_eligibility_requested is True
    assert result.routing_decision == "item_eligibility_flow"
    
def test_case_8_7_route_explanation():
    router = GeminiIntentRouter()
    query = "제3자단가계약이랑 MAS 차이가 뭐야?"
    mock_json = {
        "primary_intent": "legal_explanation",
        "slots": {}
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))
    
    assert result.primary_intent == "legal_explanation"
    assert "procurement_route_review" in result.secondary_intents
    assert result.legal_explanation_only is True
    assert "item_name" not in result.clarification_needed
    assert result.routing_decision == "legal_explanation_flow"

def test_legal_amount_question_does_not_request_company_lookup():
    router = GeminiIntentRouter()
    query = "2억 물품 수의계약 가능해?"
    mock_json = {
        "primary_intent": "contract_review",
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "amount": 200000000,
            "contract_method": "direct_contract"
        }
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))

    assert result.legal_review_required is True
    assert result.company_lookup_required is False
    assert result.candidate_lookup_required is False
    assert result.local_purchase_support_required is True
    assert "법령상 계약 가능 범위와 확인 필요사항" in result.answer_focus
    assert "부산 업체·상품 후보 조회" not in result.answer_focus

def test_specific_item_local_purchase_question_requests_both_legal_and_company_support():
    router = GeminiIntentRouter()
    query = "LED 조명 2억인데 부산업체 활용 방법 있어?"
    mock_json = {
        "primary_intent": "contract_review",
        "secondary_intents": ["local_purchase_support"],
        "confidence": 0.9,
        "slots": {
            "contract_object": "goods",
            "item_name": "LED 조명",
            "amount": 200000000,
            "location": "부산",
            "local_supplier_intent": True
        }
    }
    result = router.parse_gemini_response(query, json.dumps(mock_json))

    assert result.legal_review_required is True
    assert result.local_purchase_support_required is True
    assert result.company_lookup_required is True
    assert result.candidate_lookup_required is True
    assert "법령상 계약 가능 범위와 확인 필요사항" in result.answer_focus
    assert "부산 지역상품 구매지원 경로" in result.answer_focus
    assert "부산 업체·상품 후보 조회" in result.answer_focus
