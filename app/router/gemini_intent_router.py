import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from google import genai
from google.genai import types

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


DEFAULT_VERTEX_PROJECT = "carbide-team-457809-a8"
DEFAULT_VERTEX_LOCATION = "asia-northeast3"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _vertex_credentials_path_exists() -> bool:
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    return bool(path and Path(path).exists())


def resolve_router_client_config(api_key: Optional[str] = None) -> Dict[str, Any]:
    """Return the runtime provider config used by the Gemini intent router."""
    explicit_api_key = api_key is not None
    vertex_enabled = _env_bool("GEMINI_ROUTER_USE_VERTEX", True)
    use_vertex = vertex_enabled and not explicit_api_key and _vertex_credentials_path_exists()
    if use_vertex:
        return {
            "provider": "vertex_ai",
            "project": (
                os.environ.get("GOOGLE_CLOUD_PROJECT")
                or os.environ.get("GOOGLE_VERTEX_PROJECT")
                or os.environ.get("VERTEX_AI_PROJECT")
                or DEFAULT_VERTEX_PROJECT
            ),
            "location": (
                os.environ.get("GOOGLE_CLOUD_LOCATION")
                or os.environ.get("GOOGLE_VERTEX_LOCATION")
                or os.environ.get("VERTEX_AI_LOCATION")
                or DEFAULT_VERTEX_LOCATION
            ),
        }
    configured_api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if configured_api_key:
        return {
            "provider": "gemini_api",
            "api_key_configured": True,
        }
    return {
        "provider": "unconfigured",
        "api_key_configured": False,
        "vertex_credentials_configured": bool(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")),
        "vertex_credentials_path_exists": _vertex_credentials_path_exists(),
    }


class GeminiIntentRouter:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        self.client_config = resolve_router_client_config(api_key=api_key)
        self.provider = self.client_config.get("provider", "unconfigured")
        http_timeout_ms = int(os.environ.get("GEMINI_HTTP_TIMEOUT_MS", "20000"))
        http_options = types.HttpOptions(timeout=http_timeout_ms)
        if self.provider == "vertex_ai":
            self.client = genai.Client(
                vertexai=True,
                project=self.client_config["project"],
                location=self.client_config["location"],
                http_options=http_options,
            )
        elif self.provider == "gemini_api":
            self.client = genai.Client(api_key=self.api_key, http_options=http_options)
        else:
            self.client = None
        self.validator = DeterministicIntentValidator()
        self.pro_fallback_enabled = os.environ.get("GEMINI_PRO_FALLBACK_ENABLED", "true").lower() == "true"
        self.flash_model = os.environ.get("GEMINI_ROUTER_MODEL", "gemini-2.5-flash")
        self.pro_model = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-2.5-pro")
        self.thinking_budget = int(os.environ.get("GEMINI_ROUTER_THINKING_BUDGET", "0"))
        self.adjudicator_thinking_budget = int(os.environ.get("GEMINI_ADJUDICATOR_THINKING_BUDGET", "128"))
        self.pro_thinking_budget = int(os.environ.get("GEMINI_ROUTER_PRO_THINKING_BUDGET", "128"))

    def normalize_slots(self, parsed_dict: Dict) -> Dict:
        """Normalize intent and slot aliases."""
        if "needs_company_search" in parsed_dict and "candidate_lookup_required" not in parsed_dict:
            parsed_dict["candidate_lookup_required"] = bool(parsed_dict.get("needs_company_search"))
        if "company_lookup_required" in parsed_dict and "candidate_lookup_required" not in parsed_dict:
            parsed_dict["candidate_lookup_required"] = bool(parsed_dict.get("company_lookup_required"))

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
        if not self.client:
            return '{"primary_intent": "out_of_scope", "routing_decision": "clarification_required", "reason": "Gemini router client is not configured"}'
        
        prompt = f"{SYSTEM_PROMPT}\n\n사용자 질의: {query}"
        return self._call_gemini_prompt(prompt, model_name)

    def _call_gemini_prompt(self, prompt: str, model_name: str, thinking_budget: Optional[int] = None) -> str:
        if not self.client:
            return '{"primary_intent": "out_of_scope", "routing_decision": "clarification_required", "reason": "Gemini router client is not configured"}'

        if thinking_budget is not None:
            budget = thinking_budget
        else:
            budget = self.pro_thinking_budget if "pro" in model_name.lower() else self.thinking_budget
        response = self.client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=budget),
            ),
        )
        return response.text

    def route_with_context_card(self, query: str, context_card: Dict[str, Any]) -> RouterResult:
        """
        Adjudicate final routing from deterministic/RAG evidence.

        This path intentionally performs a single Flash call and does not use
        retry or Pro fallback. It is a latency-bounded final routing check, not
        a general-purpose answer generator.
        """
        if not self.client:
            return RouterResult(primary_intent="out_of_scope", routing_decision="clarification_required", reason="Gemini router client is not configured")

        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "추가 역할: 아래 판정 카드는 Gateway, 정규화 엔진, Keyword Router, Intent RAG의 결과다.\n"
            "너는 이 카드의 충돌·저신뢰·슬롯 누락을 검토해 최종 라우팅 JSON만 반환한다.\n"
            "최종 답변을 작성하지 말고, 법적 결론이나 기준금액을 생성하지 않는다.\n"
            "candidate_lookup_required는 사용자가 업체 후보/목록을 원하고 구체 품목이 있을 때만 true로 둔다.\n"
            "지역업체 활용 방법, 구매경로, 수의계약 가능성 검토는 순수 업체검색이 아니라 contract_review/local_purchase_support/procurement_route_review로 분류한다.\n\n"
            f"판정 카드(JSON):\n{json.dumps(context_card, ensure_ascii=False, default=str)}\n\n"
            f"사용자 질의: {query}"
        )

        try:
            response_text = self._call_gemini_prompt(
                prompt,
                self.flash_model,
                thinking_budget=self.adjudicator_thinking_budget,
            )
            router_result = self.parse_gemini_response(query, response_text)
        except Exception as e:
            logger.error(f"Adjudicator Flash call failed: {e}")
            return RouterResult(
                primary_intent="out_of_scope",
                routing_decision="clarification_required",
                reason="Gemini adjudicator API error",
            )

        return repair_slots(query, router_result)

    def route(self, query: str) -> RouterResult:
        """
        API calling, fallback, and slot repair integration.
        1. Flash -> 2. Salvage/Parse -> 3. Slot Repair -> 4. Retry -> 5. Pro Fallback
        """
        if not self.client:
            return RouterResult(primary_intent="out_of_scope", routing_decision="clarification_required", reason="Gemini router client is not configured")
            
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
