import json
from app.router.gemini_intent_router import GeminiIntentRouter

def test_json_markdown_stripping():
    router = GeminiIntentRouter()
    
    mock_response = """```json
{
  "primary_intent": "legal_explanation",
  "confidence": 0.9,
  "routing_decision": "legal_explanation_flow"
}
```"""
    
    result = router.parse_gemini_response("테스트 쿼리", mock_response)
    assert result.primary_intent == "legal_explanation"
    assert result.routing_decision == "legal_explanation_flow"
    assert result.confidence == 0.9

def test_invalid_json_fallback():
    router = GeminiIntentRouter()
    
    mock_response = "이것은 JSON이 아닙니다."
    result = router.parse_gemini_response("이상한 쿼리", mock_response)
    
    assert result.primary_intent == "out_of_scope"
    assert result.routing_decision == "clarification_required"
    assert "Failed to parse" in result.reason

def test_confidence_fallback():
    router = GeminiIntentRouter()
    mock_json = {
        "primary_intent": "legal_explanation",
        "confidence": 0.5,
        "slots": {}
    }
    
    result = router.parse_gemini_response("모호한 질문", json.dumps(mock_json))
    assert result.routing_decision == "clarification_required"
    assert "의도 불분명" in result.clarification_needed

def test_prohibited_phrases_removal():
    router = GeminiIntentRouter()
    mock_json = {
        "primary_intent": "contract_review",
        "reason": "해당 품목은 수의계약 가능합니다.",
        "slots": {}
    }
    
    result = router.parse_gemini_response("계약 문의", json.dumps(mock_json))
    assert "수의계약 가능합니다" not in result.reason
    assert "금지된 표현 제거됨" in result.reason

def test_routing_decision_auto_fill():
    router = GeminiIntentRouter()
    mock_json = {
        "primary_intent": "contract_review",
        "slots": {"buyer_name": "테스트기관", "amount": 50000000}
    }
    
    result = router.parse_gemini_response("테스트기관 5천만원 물품 구매", json.dumps(mock_json))
    assert result.routing_decision != ""
    assert result.routing_decision == "contract_review_flow"

def test_invalid_intent_schema():
    router = GeminiIntentRouter()
    mock_json = {
        "primary_intent": "non_existent_intent",
        "routing_decision": "legal_explanation_flow"
    }
    
    result = router.parse_gemini_response("테스트", json.dumps(mock_json))
    assert result.routing_decision == "clarification_required"
    assert "Schema validation failed" in getattr(result, "reason", "")

def test_invalid_routing_decision_schema():
    router = GeminiIntentRouter()
    mock_json = {
        "primary_intent": "legal_explanation",
        "routing_decision": "non_existent_flow"
    }
    
    result = router.parse_gemini_response("테스트", json.dumps(mock_json))
    assert result.routing_decision == "clarification_required"
    assert "Schema validation failed" in getattr(result, "reason", "")

def test_normalize_slots_korean_to_canonical():
    router = GeminiIntentRouter()
    mock_json = {
        "primary_intent": "contract_review",
        "slots": {
            "company_type": "여성기업",
            "quote_type": "1인견적",
            "contract_object": "물품",
            "contract_method": "수의계약"
        }
    }
    
    result = router.parse_gemini_response("테스트", json.dumps(mock_json))
    assert result.slots.company_type == "women"
    assert result.slots.quote_type == "1_quote"
    assert result.slots.contract_object == "goods"
    assert result.slots.contract_method == "direct_contract"

def test_intent_alias_normalization():
    router = GeminiIntentRouter()
    mock_json = {
        "primary_intent": "contract_procedure",
        "routing_decision": "contract_procedure_flow",
        "slots": {}
    }
    
    result = router.parse_gemini_response("테스트", json.dumps(mock_json))
    assert result.primary_intent == "contract_review"
    assert result.routing_decision == "contract_review_flow"

def test_fallback_salvage_and_repair(monkeypatch):
    router = GeminiIntentRouter(api_key="mock_key")
    
    def mock_call(query, model_name):
        return "이건 이상한 응답입니다 여성기업"
    
    monkeypatch.setattr(router, "_call_gemini", mock_call)
    
    result = router.route("여성기업 업체 찾아줘")
    assert result.slots.company_type == "women"
    assert "salvaged: True" in result.reason
    assert result.routing_decision == "local_purchase_support_flow"
    assert result.primary_intent == "local_purchase_support"

def test_fallback_pro_called(monkeypatch):
    router = GeminiIntentRouter(api_key="mock_key")
    call_counts = {"flash": 0, "pro": 0}
    
    def mock_call(query, model_name):
        if "flash" in model_name:
            call_counts["flash"] += 1
            return '{"primary_intent": "non_existent_intent"}' 
        else:
            call_counts["pro"] += 1
            return '{"primary_intent": "legal_explanation", "routing_decision": "legal_explanation_flow"}'
            
    monkeypatch.setattr(router, "_call_gemini", mock_call)
    
    result = router.route("아무 말")
    assert call_counts["flash"] == 2 
    assert call_counts["pro"] == 1   
    assert result.primary_intent == "legal_explanation"
    assert "Used Pro Fallback" in result.reason
