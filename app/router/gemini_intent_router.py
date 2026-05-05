import json
import logging
import os
from typing import Dict, Any, Optional

import google.generativeai as genai

from app.router.intent_schema import RouterResult, RouterSlots
from app.router.router_prompt import SYSTEM_PROMPT
from app.router.deterministic_intent_validator import DeterministicIntentValidator
from app.router.slot_repair import repair_slots

logger = logging.getLogger(__name__)

INTENT_ALIASES = {
    "contract_procedure": "contract_review",
    "amount_check": "contract_review",
    "vendor_search": "candidate_search",
    "supplier_search": "candidate_search",
    "item_check": "item_eligibility",
}

ROUTING_DECISION_ALIASES = {
    "contract_procedure_flow": "contract_review_flow",
    "amount_check_flow": "contract_review_flow",
    "vendor_search_flow": "candidate_search_flow",
}

COMPANY_TYPE_ALIASES = {
    "여성기업": "women",
    "장애인기업": "disabled",
    "사회적기업": "social",
    "창업기업": "startup",
    "청년창업기업": "startup",
    "소기업": "small_business",
    "소상공인": "small_business",
    "일반기업": "general",
}

QUOTE_TYPE_ALIASES = {
    "1인견적": "1_quote",
    "1인 견적": "1_quote",
    "2인견적": "2_quote",
    "2인 견적": "2_quote",
    "2인 이상 견적": "2_quote",
}

CONTRACT_OBJECT_ALIASES = {
    "물품": "goods",
    "용역": "service",
    "공사": "construction",
}

CONTRACT_METHOD_ALIASES = {
    "수의계약": "direct_contract",
    "경쟁입찰": "competitive_bid",
    "제한경쟁": "limited_competition",
    "일반경쟁": "open_competition",
}

PROCUREMENT_ROUTE_ALIASES = {
    "MAS": "mas",
    "다수공급자계약": "mas",
    "종합쇼핑몰": "shopping_mall",
    "제3자단가": "third_party_unit_price",
    "입찰": "bid",
}

class GeminiIntentRouter:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
        self.validator = DeterministicIntentValidator()
        self.pro_fallback_enabled = os.environ.get("GEMINI_PRO_FALLBACK_ENABLED", "true").lower() == "true"
        self.flash_model = os.environ.get("GEMINI_ROUTER_MODEL", "gemini-2.5-flash")
        self.pro_model = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")

    def normalize_slots(self, parsed_dict: Dict) -> Dict:
        """Normalize intent and slot aliases."""
        if "primary_intent" in parsed_dict:
            val = parsed_dict["primary_intent"]
            parsed_dict["primary_intent"] = INTENT_ALIASES.get(val, val)
            
        if "secondary_intents" in parsed_dict and isinstance(parsed_dict["secondary_intents"], list):
            parsed_dict["secondary_intents"] = [INTENT_ALIASES.get(i, i) for i in parsed_dict["secondary_intents"]]
            
        if "routing_decision" in parsed_dict:
            val = parsed_dict["routing_decision"]
            parsed_dict["routing_decision"] = ROUTING_DECISION_ALIASES.get(val, val)
            
        if "slots" in parsed_dict and isinstance(parsed_dict["slots"], dict):
            slots = parsed_dict["slots"]
            if "company_type" in slots and slots["company_type"]:
                slots["company_type"] = COMPANY_TYPE_ALIASES.get(slots["company_type"], slots["company_type"])
            if "quote_type" in slots and slots["quote_type"]:
                slots["quote_type"] = QUOTE_TYPE_ALIASES.get(slots["quote_type"], slots["quote_type"])
            if "contract_object" in slots and slots["contract_object"]:
                slots["contract_object"] = CONTRACT_OBJECT_ALIASES.get(slots["contract_object"], slots["contract_object"])
            if "contract_method" in slots and slots["contract_method"]:
                slots["contract_method"] = CONTRACT_METHOD_ALIASES.get(slots["contract_method"], slots["contract_method"])
            if "procurement_route" in slots and slots["procurement_route"]:
                slots["procurement_route"] = PROCUREMENT_ROUTE_ALIASES.get(slots["procurement_route"], slots["procurement_route"])
                
        return parsed_dict

    def _strip_json_markdown(self, text: str) -> str:
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()

    def _salvage_slots(self, raw_text: str) -> Dict:
        """Attempt to extract slot information even if JSON is severely broken."""
        salvaged = {}
        if "여성기업" in raw_text or "women" in raw_text:
            salvaged["company_type"] = "women"
        return salvaged

    def parse_gemini_response(self, query: str, response_text: str) -> RouterResult:
        """Pure function: parse JSON, normalize, and validate."""
        clean_json = self._strip_json_markdown(response_text)
        try:
            parsed_dict = json.loads(clean_json)
        except json.JSONDecodeError as e:
            salvaged = self._salvage_slots(response_text)
            return RouterResult(
                primary_intent="out_of_scope",
                routing_decision="clarification_required",
                slots=RouterSlots(**salvaged),
                reason=f"Failed to parse LLM JSON response: {str(e)} | salvaged: {bool(salvaged)}"
            )
            
        parsed_dict = self.normalize_slots(parsed_dict)
        return self.validator.validate(query, parsed_dict)

    def _call_gemini(self, query: str, model_name: str) -> str:
        if not self.api_key:
            return '{"primary_intent": "out_of_scope", "routing_decision": "clarification_required", "reason": "No API Key"}'
        
        prompt = f"{SYSTEM_PROMPT}\n\n사용자 질의: {query}"
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        return response.text

    def route(self, query: str) -> RouterResult:
        """
        API calling, fallback, and slot repair integration.
        1. Flash -> 2. Salvage/Parse -> 3. Slot Repair -> 4. Retry -> 5. Pro Fallback
        """
        if not self.api_key:
            return RouterResult(primary_intent="out_of_scope", routing_decision="clarification_required", reason="GEMINI_API_KEY is not set")
            
        api_error_summary = None
        # 1. Gemini Flash 호출
        try:
            flash_resp_text = self._call_gemini(query, self.flash_model)
            router_result = self.parse_gemini_response(query, flash_resp_text)
        except Exception as e:
            logger.error(f"Flash call failed: {e}")
            if "400 API key not valid" in str(e):
                api_error_summary = "api_key_invalid"
            else:
                api_error_summary = "api_call_failed"
                
            router_result = RouterResult(
                primary_intent="out_of_scope",
                routing_decision="clarification_required",
                reason=f"Gemini API error: {api_error_summary}"
            )

        # 2. Slot Repair 실행
        repaired_result = repair_slots(query, router_result)
        
        # API key 오류는 재시도로 복구되지 않으므로, Slot Repair 결과만 반영 후 즉시 반환
        if api_error_summary == "api_key_invalid":
            return repaired_result

        # 3. 정상 flow로 승격되었거나 명확한 out_of_scope 라면 즉시 반환 (Pro 생략)
        if repaired_result.routing_decision not in ["clarification_required", ""]:
            return repaired_result

        # 4. 여전히 clarification_required 라면 Flash Retry (1회)
        repaired_retry = repaired_result
        try:
            logger.info("Retrying Flash due to clarification_required")
            retry_text = self._call_gemini(query, self.flash_model)
            retry_result = self.parse_gemini_response(query, retry_text)
            repaired_retry = repair_slots(query, retry_result)
            if repaired_retry.routing_decision not in ["clarification_required", ""]:
                return repaired_retry
        except Exception as e:
            logger.error(f"Flash retry failed: {e}")

        # 5. 그래도 실패하면 Pro Fallback
        if not self.pro_fallback_enabled:
            return repaired_retry
            
        try:
            logger.warning("Using Pro Fallback", extra={
                "query_len": len(query),
                "fallback_reason": "schema_or_parse_failure"
            })
            pro_text = self._call_gemini(query, self.pro_model)
            pro_result = self.parse_gemini_response(query, pro_text)
            pro_repaired = repair_slots(query, pro_result)
            
            # Record that fallback was used
            reason = getattr(pro_repaired, "reason", "")
            pro_repaired.reason = (reason + " | Used Pro Fallback").strip()
            return pro_repaired
        except Exception as e:
            logger.error(f"Pro fallback failed: {e}")
            return repaired_result # return the best we had
