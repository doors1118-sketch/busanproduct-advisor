import json
import re
from typing import Dict, Any, Optional
from app.router.intent_schema import RouterResult
from app.router.router_prompt import SYSTEM_PROMPT
from app.router.deterministic_intent_validator import DeterministicIntentValidator

class GeminiIntentRouter:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.validator = DeterministicIntentValidator()
        
    def _strip_json_markdown(self, text: str) -> str:
        """Strip markdown json code block if present."""
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
            
        if text.endswith("```"):
            text = text[:-3]
            
        return text.strip()
        
    def parse_gemini_response(self, query: str, response_text: str) -> RouterResult:
        """Parse JSON response and run deterministic validator."""
        clean_json = self._strip_json_markdown(response_text)
        try:
            parsed_dict = json.loads(clean_json)
        except json.JSONDecodeError as e:
            return RouterResult(
                primary_intent="out_of_scope",
                routing_decision="clarification_required",
                reason=f"Failed to parse LLM JSON response: {str(e)}"
            )
            
        return self.validator.validate(query, parsed_dict)
        
    def route(self, query: str) -> RouterResult:
        """Actual LLM call would go here. For now we will mock this in tests."""
        # For unit testing, this method is typically mocked.
        # In actual deployment:
        # 1. Build prompt with SYSTEM_PROMPT + query
        # 2. Call Gemini API
        # 3. Return self.parse_gemini_response(query, llm_response_text)
        raise NotImplementedError("Actual Gemini API call is not implemented in this phase.")
