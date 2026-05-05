import pytest
from app.runtime.chatbot_orchestrator import run_chatbot_runtime
from app.runtime.runtime_schema import ChatbotRuntimeRequest

def test_api_error_fallback(monkeypatch):
    def mock_route(self, query, model_name):
        raise Exception("API Connection Timeout")

    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    monkeypatch.setattr("app.router.gemini_intent_router.GeminiIntentRouter._call_gemini", mock_route)
    
    req = ChatbotRuntimeRequest(user_query="1 LED ҷ", mock_gemini_response=None)
    resp = run_chatbot_runtime(req)
    
    # router_result clarification_required
    assert resp.router_result.routing_decision == "clarification_required"
    
    assert "Gemini API error: api_call_failed" in getattr(resp.router_result, "reason", "")
    
    # answer_output 
    assert resp.answer_output is not None
    assert "추가 정보 요청" in resp.answer_output.rendered_markdown or "안내" in resp.answer_output.rendered_markdown

