"""
Gemini API 해석 엔진
Korean Law MCP를 도구로 등록하여 function calling으로 법령 검색 후 답변 생성.
v1.4.4: PROMPT_MODE feature flag로 legacy/dynamic 분기
"""
import os
import re
import json
import time
import uuid
import html
from typing import Optional, Any
from dotenv import load_dotenv
import company_api

load_dotenv()

from google import genai
from google.genai import types

# Feature flag: legacy | dynamic_v1_4_4
PROMPT_MODE = os.getenv("PROMPT_MODE", "legacy")
MAX_TOOL_CALL_ROUNDS = int(os.getenv("MAX_TOOL_CALL_ROUNDS", "2"))  # MCP preflight가 데이터 사전 주입 → 2라운드 충분
LLM_TOOL_LOOP_ENABLED = os.getenv("LLM_TOOL_LOOP_ENABLED", "false").lower() == "true"
NATURAL_LANGUAGE_WRITER_ENABLED = os.getenv("NATURAL_LANGUAGE_WRITER_ENABLED", "false").lower() == "true"
NATURAL_LANGUAGE_WRITER_MODE = os.getenv("NATURAL_LANGUAGE_WRITER_MODE", "selective")
NATURAL_LANGUAGE_WRITER_MODEL = os.getenv("NATURAL_LANGUAGE_WRITER_MODEL", "gemini-2.5-flash")
NATURAL_LANGUAGE_WRITER_TIMEOUT_SEC = float(os.getenv("NATURAL_LANGUAGE_WRITER_TIMEOUT_SEC", "15"))
NATURAL_LANGUAGE_WRITER_MAX_INPUT_CHARS = int(os.getenv("NATURAL_LANGUAGE_WRITER_MAX_INPUT_CHARS", "3500"))
NATURAL_LANGUAGE_WRITER_MIN_INPUT_CHARS = int(os.getenv("NATURAL_LANGUAGE_WRITER_MIN_INPUT_CHARS", "180"))
NATURAL_LANGUAGE_WRITER_MAX_PRIOR_MODEL_MS = int(os.getenv("NATURAL_LANGUAGE_WRITER_MAX_PRIOR_MODEL_MS", "12000"))

# Legacy system prompt (PROMPT_MODE=legacy 일 때만 사용)
from system_prompt import SYSTEM_PROMPT
import mcp_client as mcp  # Korean Law MCP 원격 클라이언트

# v1.4.4 dynamic prompt modules
from prompting.keyword_pre_router import keyword_pre_route
from prompting.intent_router import classify_intent
from prompting.guardrail_selector import select_guardrails
from prompting.guardrail_sanity_check import apply_guardrail_sanity_check
from prompting.prompt_assembler import assemble_prompt, get_core_prompt_hash
from prompting.schemas import ApiStatus, LegalConclusionScope
from policies.timeout_policy import call_mcp_with_timeout, evaluate_legal_scope
from policies.company_policy import format_company_for_llm, format_company_detail_for_llm
from policies.monitoring_policy import log_routing, log_classification_failure
from policies.item_normalization_policy import (
    extract_item_keyword_with_synonyms,
    normalize_item_query,
)
from policies.purchase_route_guidance_policy import (
    build_purchase_route_cards,
    derive_candidate_table_display_options,
    format_purchase_route_guidance_for_llm,
)
from policies.regional_support_catalog import format_catalog_matches_for_llm
from policies.practice_manual_cards import (
    format_practice_manual_cards_for_llm,
    is_contract_procedure_query,
    match_contract_lifecycle_cards,
    match_practice_manual_cards,
    render_contract_lifecycle_for_answer,
    render_practice_manual_cards_for_answer,
)
from policies.pps_qa_cards import (
    format_pps_qa_cards_for_llm,
    match_pps_qa_cards,
    render_pps_qa_cards_for_answer,
)
from policies.tool_loop_gate import assess_tool_loop_gate

# Legacy regression guard: rag_dict values must be assembled with
# rag_dict.get(key, "") for key in ["law", "qa", "manual", "innovation", "tech"].

# 인용 조문 저장 (답변 후 다운로드용)
_cited_laws = []

# API 레이어용 generation_meta 저장 (매 chat 호출 후 업데이트)
_last_generation_meta = {}
_current_routing_confidence_meta = {}
_current_tool_loop_gate_meta = {}
_current_intent_rag_meta = {}
_current_evidence_context_meta = {}
_current_llm_payload_meta = {}

from cachetools import TTLCache
_mcp_cache = TTLCache(maxsize=100, ttl=3600)

# Legacy 경로에서도 Gemini Intent Router를 "질문 분석 보조자"로 사용한다.
# 최종 경로 결정은 기존 규칙 라우터가 담당하고, Router 결과는 품목/업체검색 필요성
# 같은 문맥 판단에만 보수적으로 반영한다.
USE_GEMINI_INTENT_ROUTER_IN_LEGACY = os.getenv(
    "USE_GEMINI_INTENT_ROUTER_IN_LEGACY", "true"
).lower() == "true"
USE_GEMINI_ROUTE_ADJUDICATOR = os.getenv(
    "USE_GEMINI_ROUTE_ADJUDICATOR",
    os.getenv("USE_GEMINI_INTENT_ROUTER_IN_LEGACY", "true"),
).lower() == "true"
GEMINI_ROUTE_ADJUDICATOR_TIMEOUT_SEC = float(os.getenv("GEMINI_ROUTE_ADJUDICATOR_TIMEOUT_SEC", "3"))

GENERIC_ITEM_TERMS = {
    "물품", "제품", "상품", "품목", "용역", "공사", "서비스", "장비", "비품",
    "수의", "수의계약", "계약", "구매", "구입", "납품", "발주", "지역상품",
    "지역업체", "부산업체", "업체", "지역제한", "입찰", "MAS", "mas",
    "다수공급자계약", "종합쇼핑몰", "나라장터", "제3자단가", "활용", "방법",
    "살", "사", "수", "있나", "있어", "있는지", "에서", "으로", "로",
}

LEGAL_EVIDENCE_TOOL_NAMES = {
    "search_law",
    "get_law_text",
    "search_interpretations",
    "search_decisions",
    "get_annexes",
    "chain_full_research",
    "chain_action_basis",
    "chain_law_system",
    "search_admin_rule",
    "get_admin_rule",
    "chain_procedure_detail",
    "chain_ordinance_compare",
    "chain_amendment_track",
    "chain_document_review",
    "get_decision_text",
}


def _env_int_value(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _normalize_evidence_context_mode(value: str | None) -> str:
    mode = (value or "shadow").strip().lower()
    aliases = {
        "legacy": "raw",
        "off": "raw",
        "none": "raw",
        "cards": "card",
        "compressed": "card",
        "evidence_card": "card",
        "evidence_cards": "card",
        "card_only": "card",
        "raw_plus_card": "dual",
        "card_plus_raw": "dual",
        "compare": "shadow",
    }
    mode = aliases.get(mode, mode)
    if mode not in {"raw", "shadow", "card", "dual"}:
        return "shadow"
    return mode


def _evidence_context_mode(env_name: str = "EVIDENCE_CONTEXT_MODE") -> str:
    return _normalize_evidence_context_mode(os.getenv(env_name, os.getenv("EVIDENCE_CONTEXT_MODE", "shadow")))


def _select_evidence_context(
    *,
    raw_context: str,
    card_context: str,
    mode: str,
    prefix: str,
    cards: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Choose what the LLM sees while keeping raw/card comparison telemetry."""
    raw_context = raw_context or ""
    card_context = card_context or ""
    requested_mode = _normalize_evidence_context_mode(mode)
    dual_raw_limit = _env_int_value("EVIDENCE_CONTEXT_DUAL_RAW_CHARS", 3000)
    min_raw_chars_for_card = _env_int_value("EVIDENCE_CONTEXT_MIN_RAW_CHARS", 2000)
    allow_longer_card = os.getenv("EVIDENCE_CONTEXT_ALLOW_LONGER_CARD", "false").lower() == "true"
    card_is_useful = bool(card_context) and (
        allow_longer_card
        or len(card_context) < len(raw_context)
        or len(raw_context) >= min_raw_chars_for_card
    )

    if requested_mode == "card" and card_is_useful:
        selected = card_context
        applied_mode = "card"
    elif requested_mode == "dual" and card_context:
        raw_tail = raw_context[:dual_raw_limit]
        selected = (
            f"{card_context}\n\n"
            f"### [원문 대조 발췌 — QA 비교용, 최대 {dual_raw_limit}자]\n{raw_tail}"
        ).strip()
        applied_mode = "dual"
    else:
        selected = raw_context
        if requested_mode in {"raw", "shadow"}:
            applied_mode = "raw"
        elif not card_context:
            applied_mode = "raw_fallback_no_card"
        else:
            applied_mode = "raw_fallback_card_not_shorter"

    raw_chars = len(raw_context)
    card_chars = len(card_context)
    selected_chars = len(selected)
    hit_count = sum(1 for card in cards or [] if card.get("status") == "hit")
    miss_count = sum(1 for card in cards or [] if card.get("status") != "hit")
    compression_ratio = round(card_chars / raw_chars, 3) if raw_chars else 0.0
    savings_pct = round((1 - (selected_chars / raw_chars)) * 100, 1) if raw_chars else 0.0

    return selected, {
        f"{prefix}_mode_requested": requested_mode,
        f"{prefix}_mode_applied": applied_mode,
        f"{prefix}_comparison_enabled": requested_mode in {"shadow", "card", "dual"},
        f"{prefix}_raw_chars": raw_chars,
        f"{prefix}_card_chars": card_chars,
        f"{prefix}_llm_chars": selected_chars,
        f"{prefix}_card_to_raw_ratio": compression_ratio,
        f"{prefix}_char_savings_pct": savings_pct,
        f"{prefix}_card_hit_count": hit_count,
        f"{prefix}_card_miss_count": miss_count,
        f"{prefix}_card_allowed_when_longer": allow_longer_card,
        f"{prefix}_min_raw_chars_for_card": min_raw_chars_for_card,
    }


def _function_args_dict(function_call) -> dict[str, Any]:
    try:
        return dict(function_call.args) if function_call.args else {}
    except Exception:
        return {}


def _text_char_len(value) -> int:
    return len(value or "") if isinstance(value, str) else len(str(value or ""))


def _content_text_chars(contents) -> int:
    total = 0
    for content in contents or []:
        for part in getattr(content, "parts", []) or []:
            text = getattr(part, "text", None)
            if text:
                total += len(text)
            function_response = getattr(part, "function_response", None)
            if function_response is not None:
                total += len(str(function_response))
            function_call = getattr(part, "function_call", None)
            if function_call is not None:
                total += len(str(function_call))
    return total


def _is_legal_evidence_tool(tool_name: str) -> bool:
    return (tool_name or "") in LEGAL_EVIDENCE_TOOL_NAMES


def _build_llm_tool_response(
    function_call,
    result_str: str,
    *,
    selected_reason: str = "llm_tool_loop",
) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    """Return the tool payload for Gemini plus compact comparison metadata.

    ``result_str`` remains the server-side raw result in all_tool_results.  Only
    the payload sent back into Gemini is switched by EVIDENCE_TOOL_RESPONSE_MODE.
    """
    tool_name = getattr(function_call, "name", "")
    if not _is_legal_evidence_tool(tool_name):
        return result_str, None, {}

    args = _function_args_dict(function_call)
    evidence_card = None
    card_context = ""
    try:
        from policies.legal_evidence_cards import build_evidence_card, render_evidence_card_context

        evidence_card = build_evidence_card(
            tool_name=tool_name,
            args=args,
            result=result_str,
            from_cache=False,
            elapsed_ms=0,
            selected_reason=selected_reason,
        )
        card_context = render_evidence_card_context(
            [evidence_card],
            max_cards=1,
            excerpt_limit=_env_int_value("EVIDENCE_CONTEXT_EXCERPT_CHARS", 450),
        )
    except Exception as e:
        print(f"  [EVIDENCE-CONTEXT] tool response card skipped: {e}", flush=True)

    mode = _evidence_context_mode("EVIDENCE_TOOL_RESPONSE_MODE")
    selected, meta = _select_evidence_context(
        raw_context=result_str,
        card_context=card_context,
        mode=mode,
        prefix="tool_response_context",
        cards=[evidence_card] if evidence_card else [],
    )
    meta["tool_response_context_tool_name"] = tool_name
    meta["tool_response_context_compressed_for_llm"] = selected != (result_str or "")
    return selected, evidence_card, meta


def _summarize_tool_response_context(all_tool_results: list[dict[str, Any]]) -> dict[str, Any]:
    raw_chars = 0
    llm_chars = 0
    card_count = 0
    compressed_count = 0
    modes: dict[str, int] = {}

    for item in all_tool_results or []:
        raw_len = int(item.get("raw_result_chars", len(str(item.get("result", ""))) if item.get("result") is not None else 0) or 0)
        llm_len = int(item.get("llm_result_chars", raw_len) or 0)
        raw_chars += raw_len
        llm_chars += llm_len
        if item.get("evidence_card"):
            card_count += 1
        if item.get("tool_response_context_compressed_for_llm"):
            compressed_count += 1
        mode = item.get("tool_response_context_mode_applied")
        if mode:
            modes[mode] = modes.get(mode, 0) + 1

    if not raw_chars and not llm_chars:
        return {}

    return {
        "tool_response_context_raw_chars": raw_chars,
        "tool_response_context_llm_chars": llm_chars,
        "tool_response_context_char_savings_pct": round((1 - (llm_chars / raw_chars)) * 100, 1) if raw_chars else 0.0,
        "tool_response_context_card_count": card_count,
        "tool_response_context_compressed_count": compressed_count,
        "tool_response_context_modes": modes,
    }


def _run_legacy_gemini_intent_router(user_message: str):
    """현재 legacy 파이프라인 안에서 Gemini Router를 보조 분석기로 실행한다.

    실패하면 None을 반환하여 기존 keyword router만으로 계속 진행한다.
    """
    if not USE_GEMINI_INTENT_ROUTER_IN_LEGACY:
        return None
    try:
        try:
            from app.router.gemini_intent_router import GeminiIntentRouter
        except ImportError:
            from router.gemini_intent_router import GeminiIntentRouter

        result = GeminiIntentRouter().route(user_message)
        print(
            "  [GEMINI-INTENT] "
            f"primary={result.primary_intent} "
            f"secondary={result.secondary_intents} "
            f"decision={result.routing_decision} "
            f"candidate_lookup={result.candidate_lookup_required} "
            f"item={result.slots.item_name}"
        )
        return result
    except Exception as e:
        print(f"  [GEMINI-INTENT] skipped: {e}")
        return None


def _run_llm_route_adjudicator(user_message: str, context_card: dict):
    """Run Gemini as a latency-bounded final route adjudicator."""
    if not USE_GEMINI_ROUTE_ADJUDICATOR:
        return None, {
            "enabled": False,
            "called": False,
            "status": "disabled",
        }

    start = time.time()
    executor = None
    try:
        try:
            from app.router.gemini_intent_router import GeminiIntentRouter
        except ImportError:
            from router.gemini_intent_router import GeminiIntentRouter
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(
            lambda: GeminiIntentRouter().route_with_context_card(user_message, context_card)
        )
        try:
            result = future.result(timeout=GEMINI_ROUTE_ADJUDICATOR_TIMEOUT_SEC)
        except FutureTimeout:
            future.cancel()
            elapsed_ms = int((time.time() - start) * 1000)
            print(
                f"  [LLM-ADJUDICATOR] timeout after {elapsed_ms}ms",
                flush=True,
            )
            return None, {
                "enabled": True,
                "called": True,
                "status": "timeout",
                "elapsed_ms": elapsed_ms,
                "timeout_sec": GEMINI_ROUTE_ADJUDICATOR_TIMEOUT_SEC,
            }

        elapsed_ms = int((time.time() - start) * 1000)
        result_reason = str(getattr(result, "reason", "") or "")
        if (
            "GEMINI_API_KEY is not set" in result_reason
            or "Gemini router client is not configured" in result_reason
            or "Gemini adjudicator API error" in result_reason
        ):
            print(
                f"  [LLM-ADJUDICATOR] unavailable: {result_reason[:120]}",
                flush=True,
            )
            return None, {
                "enabled": True,
                "called": True,
                "status": "unavailable",
                "elapsed_ms": elapsed_ms,
                "reason": result_reason[:300],
            }
        print(
            "  [LLM-ADJUDICATOR] "
            f"primary={getattr(result, 'primary_intent', '')} "
            f"secondary={list(getattr(result, 'secondary_intents', []) or [])} "
            f"decision={getattr(result, 'routing_decision', '')} "
            f"candidate_lookup={bool(getattr(result, 'candidate_lookup_required', False))} "
            f"elapsed_ms={elapsed_ms}",
            flush=True,
        )
        return result, {
            "enabled": True,
            "called": True,
            "status": "success",
            "elapsed_ms": elapsed_ms,
            "timeout_sec": GEMINI_ROUTE_ADJUDICATOR_TIMEOUT_SEC,
        }
    except Exception as e:
        elapsed_ms = int((time.time() - start) * 1000)
        print(f"  [LLM-ADJUDICATOR] failed: {e}", flush=True)
        return None, {
            "enabled": True,
            "called": True,
            "status": "failed",
            "elapsed_ms": elapsed_ms,
            "error": str(e)[:300],
        }
    finally:
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=True)


def _labels_from_router_adjudication(router_result, user_message: str = "") -> list[str]:
    """Translate RouterResult intents into legacy routing labels."""
    if router_result is None:
        return []

    labels: list[str] = []

    def add(*values: str) -> None:
        for value in values:
            if value and value not in labels:
                labels.append(value)

    intents = [getattr(router_result, "primary_intent", "")] + list(getattr(router_result, "secondary_intents", []) or [])
    for intent in intents:
        if intent == "legal_explanation":
            add("legal_explanation", "common_procurement")
        elif intent == "contract_review":
            add("contract_review")
        elif intent == "local_purchase_support":
            add("local_purchase_support")
        elif intent == "candidate_search":
            add("company_search")
        elif intent == "item_eligibility":
            add("item_eligibility", "certified_product_search")
        elif intent == "procurement_route_review":
            add("procurement_route_review", "mas_shopping_mall")
        elif intent == "mixed":
            add("mixed_contract")

    slots = getattr(router_result, "slots", None)
    contract_object = getattr(slots, "contract_object", None) if slots else None
    if contract_object == "goods":
        add("item_purchase")
    elif contract_object == "service":
        add("service_contract")
    elif contract_object == "construction":
        add("construction_contract")

    if bool(getattr(router_result, "candidate_lookup_required", False)) and not _is_legal_definition_query(user_message):
        add("company_search")

    return labels


def _apply_router_adjudication_to_labels(intent_labels: list[str], router_result, user_message: str) -> tuple[list[str], dict]:
    """Apply validated LLM adjudication as final routing signal."""
    before = list(intent_labels or [])
    labels = list(dict.fromkeys(before))
    additions = _labels_from_router_adjudication(router_result, user_message)
    for label in additions:
        if label not in labels:
            labels.append(label)

    removed: list[str] = []
    if router_result is not None:
        router_intents = [getattr(router_result, "primary_intent", "")] + list(getattr(router_result, "secondary_intents", []) or [])
        candidate_intent = "candidate_search" in router_intents or bool(getattr(router_result, "candidate_lookup_required", False))
        if not candidate_intent and "company_search" in labels:
            try:
                try:
                    from app.router.intent_normalization import normalize_query_intent
                except ImportError:
                    from router.intent_normalization import normalize_query_intent
                norm = normalize_query_intent(user_message)
                if norm.company_lookup_blocked or not norm.company_lookup_requested:
                    labels = [label for label in labels if label != "company_search"]
                    removed.append("company_search")
            except Exception:
                pass

    return labels, {
        "labels_before": before,
        "labels_added": [label for label in additions if label not in before],
        "labels_removed": removed,
        "labels_after": labels,
    }


def _should_skip_gemini_intent_router(user_message: str, gateway_decision=None) -> bool:
    """Skip LLM intent routing for clear amount/contract questions."""
    compact = (user_message or "").replace(" ", "")
    has_amount_case = (
        bool(gateway_decision and "amount_case_question" in getattr(gateway_decision, "exclusions", []))
        or _parse_amount(user_message) is not None
    )
    has_contract_method = any(term in compact for term in ("수의계약", "입찰", "지역제한", "견적"))
    has_local_or_company = any(term in compact for term in ("부산업체", "지역업체", "업체후보", "추천", "찾아", "검색"))
    if has_amount_case and has_contract_method and not has_local_or_company:
        return True
    if has_amount_case and has_local_or_company:
        item = _resolve_company_item_query(user_message, None)
        return _is_specific_item_keyword(item)
    return False


def _router_result_to_meta(router_result) -> dict:
    if router_result is None:
        return {"enabled": USE_GEMINI_INTENT_ROUTER_IN_LEGACY, "status": "not_available"}
    slots = getattr(router_result, "slots", None)
    return {
        "enabled": USE_GEMINI_INTENT_ROUTER_IN_LEGACY,
        "status": "success",
        "primary_intent": getattr(router_result, "primary_intent", ""),
        "secondary_intents": list(getattr(router_result, "secondary_intents", []) or []),
        "routing_decision": getattr(router_result, "routing_decision", ""),
        "candidate_lookup_required": bool(getattr(router_result, "candidate_lookup_required", False)),
        "company_lookup_required": bool(getattr(router_result, "company_lookup_required", False)),
        "legal_review_required": bool(getattr(router_result, "legal_review_required", False)),
        "local_purchase_support_required": bool(getattr(router_result, "local_purchase_support_required", False)),
        "answer_focus": list(getattr(router_result, "answer_focus", []) or []),
        "confidence": getattr(router_result, "confidence", None),
        "item_name": getattr(slots, "item_name", None) if slots else None,
        "contract_object": getattr(slots, "contract_object", None) if slots else None,
        "amount": getattr(slots, "amount", None) if slots else None,
        "contract_method": getattr(slots, "contract_method", None) if slots else None,
        "location": getattr(slots, "location", None) if slots else None,
    }


def _resolve_intent_rag_context(user_message: str):
    """Resolve local Intent RAG context. Fail-open to existing routing."""
    try:
        try:
            from router.intent_rag_resolver import resolve_intent_context
        except ImportError:
            from app.router.intent_rag_resolver import resolve_intent_context
        decision = resolve_intent_context(user_message)
        print(
            "  [INTENT-RAG] "
            f"primary={decision.primary_intent} "
            f"labels={list(decision.intent_labels)} "
            f"mode={decision.answer_mode} "
            f"confidence={decision.confidence:.2f} "
            f"company_required={decision.company_search_required} "
            f"blocked={decision.company_search_blocked}",
            flush=True,
        )
        return decision
    except Exception as e:
        print(f"  [INTENT-RAG] skipped: {e}", flush=True)
        return None


def _intent_rag_prefixed_meta(decision) -> dict:
    if decision is None:
        return {
            "intent_rag_enabled": True,
            "intent_rag_status": "not_available",
        }
    try:
        raw = decision.to_meta()
    except Exception:
        return {
            "intent_rag_enabled": True,
            "intent_rag_status": "serialize_failed",
        }
    return {
        "intent_rag_enabled": bool(raw.get("enabled", True)),
        "intent_rag_status": raw.get("status", ""),
        "intent_rag_primary_intent": raw.get("primary_intent", ""),
        "intent_rag_labels": raw.get("intent_labels", []),
        "intent_rag_sub_intents": raw.get("sub_intents", []),
        "intent_rag_answer_mode": raw.get("answer_mode", ""),
        "intent_rag_confidence": raw.get("confidence", 0.0),
        "intent_rag_confidence_level": raw.get("confidence_level", ""),
        "intent_rag_company_search_required": raw.get("company_search_required", False),
        "intent_rag_company_search_blocked": raw.get("company_search_blocked", False),
        "intent_rag_local_purchase_support_required": raw.get("local_purchase_support_required", False),
        "intent_rag_contract_review_required": raw.get("contract_review_required", False),
        "intent_rag_procedure_required": raw.get("procedure_required", False),
        "intent_rag_legal_basis_required": raw.get("legal_basis_required", False),
        "intent_rag_llm_router_required": raw.get("llm_router_required", True),
        "intent_rag_corpus_record_count": raw.get("corpus_record_count", 0),
        "intent_rag_item_name": raw.get("item_name", ""),
        "intent_rag_contract_object": raw.get("contract_object", ""),
        "intent_rag_amount": raw.get("amount"),
        "intent_rag_reasons": raw.get("reasons", []),
        "intent_rag_matched_examples": raw.get("matched_examples", []),
    }


def _build_intent_rag_guidance_context(decision) -> str:
    try:
        try:
            from router.intent_rag_resolver import format_intent_context_for_llm
        except ImportError:
            from app.router.intent_rag_resolver import format_intent_context_for_llm
        return format_intent_context_for_llm(decision)
    except Exception:
        return ""


def _is_specific_item_keyword(value: str) -> bool:
    """업체 API 검색에 넣을 수 있는 구체 품목인지 보수적으로 판정한다."""
    if not value:
        return False
    text = str(value).strip()
    if not text:
        return False

    # 금액/계약방식/일반명사를 제거했을 때 남는 실질 품목명이 있어야 한다.
    cleaned = re.sub(r'\d+\s*(억|억원|천만|천만원|백만|백만원|만|만원)\s*원?', ' ', text)
    cleaned = re.sub(r'[?!.,"\'“”‘’()\[\]{}]', ' ', cleaned)
    cleaned = re.sub(r'(MAS|다수공급자계약|종합쇼핑몰|나라장터|제3자단가)', ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'(지역제한|지역업체|부산업체|부산\s*업체|업체|입찰|활용|방법|구매|구입|계약|발주|납품)', ' ', cleaned)
    tokens = [t.strip() for t in re.split(r'\s+', cleaned) if t.strip()]
    meaningful = [t for t in tokens if t not in GENERIC_ITEM_TERMS]
    if not meaningful:
        return False

    # "2억 물품 수의"처럼 일반명사만 섞인 경우 방지
    compact = "".join(meaningful)
    return len(compact) >= 2


def _get_router_item_query(router_result) -> str:
    slots = getattr(router_result, "slots", None)
    if not slots:
        return ""
    for attr in ("item_name", "service_type", "construction_type"):
        val = getattr(slots, attr, None)
        if _is_specific_item_keyword(val):
            return str(val).strip()
    return ""


def _get_router_contract_object(router_result, user_message: str = "") -> str:
    slots = getattr(router_result, "slots", None)
    value = getattr(slots, "contract_object", None) if slots else None
    if value in ("goods", "service", "construction"):
        return value
    q = user_message or ""
    if any(term in q for term in ("용역", "위탁", "유지관리", "청소", "경비", "설계", "감리", "컨설팅")):
        return "service"
    if any(term in q for term in ("공사", "시공", "전기공사", "소방공사", "건축공사", "토목공사", "설비공사")):
        return "construction"
    return "goods"


def _build_router_guidance_context(router_result) -> str:
    """LLM 답변 초점을 Router 분석 결과와 맞추기 위한 짧은 운영 지침."""
    if router_result is None:
        return ""
    slots = getattr(router_result, "slots", None)
    focus = list(getattr(router_result, "answer_focus", []) or [])
    if not focus:
        return ""

    lines = [
        "### [질문 인식 결과 — 답변 방향]",
        f"- 주 의도: {getattr(router_result, 'primary_intent', '')}",
        f"- 보조 의도: {', '.join(list(getattr(router_result, 'secondary_intents', []) or [])) or '없음'}",
        f"- 답변 초점: {', '.join(focus)}",
        f"- 법령 검토 필요: {bool(getattr(router_result, 'legal_review_required', False))}",
        f"- 지역상품 구매지원 관점 필요: {bool(getattr(router_result, 'local_purchase_support_required', False))}",
        f"- 업체 후보 조회 필요: {bool(getattr(router_result, 'company_lookup_required', False) or getattr(router_result, 'candidate_lookup_required', False))}",
    ]
    if slots:
        item = getattr(slots, "item_name", None) or getattr(slots, "service_type", None) or getattr(slots, "construction_type", None)
        if item:
            lines.append(f"- 구체 품목: {item}")
        if getattr(slots, "amount", None):
            lines.append(f"- 금액: {getattr(slots, 'amount')}")
        if getattr(slots, "contract_method", None):
            lines.append(f"- 계약방식: {getattr(slots, 'contract_method')}")
    lines.append("- 위 분석은 답변 방향 지침이며, 법적 결론은 수집된 법령 근거와 확인 필요사항을 기준으로 제한적으로 작성한다.")
    return "\n".join(lines)


def _resolve_company_item_query(user_message: str, router_result=None) -> str:
    """업체 검색용 품목명 결정. Gemini Router 슬롯을 우선하고 기존 추출기는 fallback."""
    router_query = _get_router_item_query(router_result)
    normalized = normalize_item_query(user_message, router_query)
    if normalized.found:
        return normalized.primary_search_term

    extracted = _extract_item_keyword(user_message)
    if _is_specific_item_keyword(extracted):
        return extracted
    return ""


def _is_explicit_company_lookup(user_message: str) -> bool:
    """사용자가 업체 후보/목록 조회를 명시했는지 보수적으로 판단한다."""
    try:
        from app.router.intent_normalization import normalize_query_intent
    except Exception:
        try:
            from router.intent_normalization import normalize_query_intent
        except Exception:
            normalize_query_intent = None

    if normalize_query_intent is not None:
        norm = normalize_query_intent(user_message)
        return bool(norm.company_lookup_requested and not norm.company_lookup_blocked)

    compact = re.sub(r"\s+", "", user_message or "").lower()
    if not compact:
        return False
    if re.search(r"(업체명|업체추천|업체후보|후보|목록|리스트|업체검색|검색|조회)(?:은|는)?(?:필요없|빼|제외|말고|하지마)", compact):
        return False
    explicit_terms = (
        "업체추천", "기업추천", "업체후보", "기업후보", "후보추천",
        "업체목록", "기업목록", "업체리스트", "기업리스트", "업체명",
        "공급업체", "납품업체", "등록업체", "조달등록업체",
    )
    if any(term in compact for term in explicit_terms):
        return True
    has_company_subject = any(term in compact for term in ("업체", "기업", "공급사", "납품사"))
    has_lookup_verb = any(term in compact for term in ("추천", "후보", "목록", "리스트", "찾아", "검색", "조회", "보여"))
    strategy_terms = ("방법", "제도", "검토", "참여", "활용", "우대", "가점", "지역제한", "어떻게")
    return bool(has_company_subject and has_lookup_verb and not any(term in compact for term in strategy_terms))


def _should_prefetch_company_routes(user_message: str, router_result=None, intent_rag_decision=None, route_plan=None) -> tuple[bool, str, str]:
    """Tier 2 업체 멀티검색 실행 여부를 결정한다.

    원칙: 구체 품목이 있고, 사용자가 지역업체/후보/구매전략을 묻는 경우만 업체 검색한다.
    """
    query = _resolve_company_item_query(user_message, router_result)
    if not query:
        return False, "", "no_specific_item"

    if route_plan is not None:
        company_mode = getattr(route_plan, "company_search_mode", "none")
        if company_mode in ("candidates_only", "route_relevant_candidates"):
            return True, query, f"route_plan_company_prefetch:{company_mode}"
        if company_mode == "none" and not _is_explicit_company_lookup(user_message):
            return False, query, "route_plan_no_company_lookup"

    if intent_rag_decision is not None:
        intent_confidence = float(getattr(intent_rag_decision, "confidence", 0.0) or 0.0)
        if (
            intent_confidence >= 0.6
            and bool(getattr(intent_rag_decision, "company_search_required", False))
        ):
            return True, query, "intent_rag_company_prefetch_required"
        if (
            intent_confidence >= 0.7
            and bool(getattr(intent_rag_decision, "company_search_blocked", False))
            and not _is_explicit_company_lookup(user_message)
        ):
            return False, query, "intent_rag_blocks_company_lookup"

    fallback_company_intent = any(
        kw in user_message
        for kw in ["지역업체", "부산업체", "부산 업체", "업체", "후보", "추천", "찾아", "있어", "있는지"]
    )
    fallback_purchase_case_intent = (
        _parse_amount(user_message) is not None
        and any(kw in user_message for kw in ["사려고", "살려고", "하려고", "맡기", "구매", "구입", "발주", "납품", "용역", "공사", "어떻게"])
    )

    if router_result is not None:
        slots = getattr(router_result, "slots", None)
        candidate_required = bool(getattr(router_result, "candidate_lookup_required", False))
        local_intent = bool(getattr(slots, "local_supplier_intent", False)) if slots else False
        routing_decision = getattr(router_result, "routing_decision", "")
        secondary = list(getattr(router_result, "secondary_intents", []) or [])
        company_related = (
            candidate_required
            or local_intent
            or routing_decision in ("candidate_search_flow", "local_purchase_support_flow", "mixed_flow")
            or "candidate_search" in secondary
            or "local_purchase_support" in secondary
        )
        if not company_related:
            # Router가 실패/불명확했지만 사용자가 명시적으로 업체·부산업체를 물은 경우는 기존 규칙으로 보완한다.
            if fallback_company_intent and routing_decision in ("clarification_required", "out_of_scope", ""):
                return True, query, "fallback_keyword_after_router_unclear"
            if fallback_purchase_case_intent and routing_decision in ("contract_review_flow", "local_purchase_support_flow", "mixed_flow", ""):
                return True, query, "amount_item_purchase_case_support"
            return False, query, "router_says_company_lookup_not_required"
        return True, query, "router_company_lookup_required"

    if fallback_company_intent:
        return True, query, "fallback_keyword_company_intent"
    if fallback_purchase_case_intent:
        return True, query, "amount_item_purchase_case_support"
    return False, query, "fallback_no_company_intent"


def _route_plan_needs(route_plan, *needs: str) -> bool:
    if route_plan is None:
        return False
    retrieval_needs = set(getattr(route_plan, "retrieval_needs", ()) or ())
    return any(need in retrieval_needs for need in needs)


def _route_plan_execution_mode(route_plan) -> str:
    return str(getattr(route_plan, "execution_mode", "") or "")


def _should_fast_track_from_route_plan(route_plan, routing_confidence_meta: dict, query_tier: int) -> bool:
    if route_plan is None:
        return query_tier == 0
    if routing_confidence_meta.get("routing_confidence_action") == "avoid_fast_track":
        return False
    return (
        bool(getattr(route_plan, "use_fast_track", False))
        and _route_plan_execution_mode(route_plan) == "company_fast_track"
        and getattr(route_plan, "company_search_mode", "") == "candidates_only"
    )


def _should_run_legal_preflight_from_route_plan(route_plan, query_tier: int) -> bool:
    if route_plan is None:
        return query_tier in (1, 2)
    return (
        bool(getattr(route_plan, "legal_review_required", False))
        or _route_plan_needs(route_plan, "legal_basis", "regional_support_catalog")
        or _route_plan_execution_mode(route_plan) in {"evidence_prefetch", "agency_specific"}
    )


def _should_run_multi_route_prefetch_from_route_plan(route_plan, query_tier: int, amount_detected) -> bool:
    if amount_detected is None:
        return False
    if route_plan is None:
        return query_tier == 2
    return (
        getattr(route_plan, "company_search_mode", "") == "route_relevant_candidates"
        or _route_plan_needs(route_plan, "purchase_route_cards", "company_candidates")
    )


def _is_legal_definition_query(user_message: str) -> bool:
    """'지역업체 정의'처럼 업체 단어가 있어도 법령/예규 설명이어야 하는 질문."""
    q = user_message.lower()
    definition_terms = ["정의", "뜻", "의미", "무슨 말", "무엇", "뭐야", "요건", "기준"]
    legal_context_terms = [
        "법", "시행령", "시행규칙", "예규", "고시", "훈령", "조례", "자치법규",
        "계약집행기준", "낙찰자 결정기준", "조문", "제",
    ]
    return any(term in q for term in definition_terms) and any(term in q for term in legal_context_terms)


def _try_legal_definition_fast_answer(user_message: str) -> str:
    """짧은 정의 질문은 내부 행정규칙 원문으로 결정적 답변을 만든다."""
    if not _is_legal_definition_query(user_message):
        return ""
    if "지역업체" not in user_message or "계약집행기준" not in user_message:
        return ""
    try:
        raw = mcp.search_admin_rule("지방자치단체 입찰 및 계약집행기준")
    except Exception:
        return ""
    match = re.search(r"지역업체[:：]\s*([^。\n]+)", raw)
    definition = match.group(1).strip() if match else ""
    if not definition:
        return ""
    definition_sentence = definition
    if not re.search(r"(말한다|의미한다|뜻한다)[.。]?$", definition_sentence):
        definition_sentence = f"{definition_sentence}를 말합니다"
    definition_sentence = definition_sentence.rstrip(".。")
    return (
        f"**지역업체**는 「지방자치단체 입찰 및 계약집행기준」상 **{definition_sentence}**.\n\n"
        "실무상으로는 입찰참가자격, 지역제한, 지역업체 참여도 평가 등을 볼 때 "
        "`주된 영업소가 어디에 있는지`를 판단하는 기준으로 쓰입니다.\n\n"
        "적용할 때는 사업장 소재지 증빙, 공고일 기준 소재지 요건, 계약유형별 세부 기준을 함께 확인해야 합니다. "
        "단순히 부산에 지점이나 영업소가 있다는 사정만으로 항상 지역업체로 인정되는 것은 아닙니다.\n\n"
        "⚖️ 본 답변은 내부 DB에 적재된 행정규칙 원문을 바탕으로 한 참고 안내입니다."
    )


def _is_regional_restriction_standard_query(user_message: str) -> bool:
    """지역제한경쟁입찰의 대표 기준금액 질문은 결정형 답변으로 처리한다."""
    q = user_message.replace(" ", "")
    has_regional_limit = "지역제한" in q or "지역제한경쟁" in q
    has_construction = any(term in q for term in ("종합공사", "건설공사"))
    has_standard_ask = any(term in q for term in ("기준", "금액", "얼마", "몇억", "100억", "150억", "88억"))
    return has_regional_limit and has_construction and has_standard_ask


def _try_regional_restriction_standard_fast_answer(user_message: str) -> str:
    """국가/공기업/지방 종합공사 지역제한 기준금액을 근거와 함께 즉시 답한다."""
    if not _is_regional_restriction_standard_query(user_message):
        return ""
    from policies.deterministic_legal_answer_gate import match_deterministic_legal_answer

    answer = match_deterministic_legal_answer(user_message)
    return answer.answer if answer else ""


def _is_practice_priority_question(user_message: str) -> bool:
    """Questions that should use practice/RoutePlan guidance before PPS Q&A."""
    q = (user_message or "").replace(" ", "").lower()
    if not q:
        return False
    checks = [
        ("디자인" in q and "인쇄" in q),
        (any(term in q for term in ("분리발주", "분할발주", "쪼개기", "나눠발주", "묶어발주"))),
        ("부대공사" in q),
        (any(term in q for term in ("공사용자재", "관급자재", "직접구매"))),
        (any(term in q for term in ("특정브랜드", "특정상표", "브랜드")) and any(term in q for term in ("규격서", "동등", "부당제한"))),
        (all(term in q for term in ("추정가격", "예정가격"))),
        (any(term in q for term in ("계약절차", "구매절차", "흐름", "단계", "순서", "처음부터"))),
        (any(term in q for term in ("소방시설공사", "정보통신공사", "조경공사", "포장공사"))),
        (any(term in q for term in ("국가기관", "국가계약", "공기업", "준정부", "공공기관")) and "지방계약" in q),
    ]
    return any(checks)


def _build_pps_qa_interpretation_fast_answer(user_message: str, intent_rag_decision=None) -> tuple[str, list[dict]]:
    """조달청 Q&A 해석사례형 질문은 LLM 루프 전에 카드 기반으로 답한다."""
    if _is_practice_priority_question(user_message):
        return "", []
    if intent_rag_decision is None:
        return "", []
    if getattr(intent_rag_decision, "answer_mode", "") != "pps_qa_interpretation":
        return "", []
    if float(getattr(intent_rag_decision, "confidence", 0.0) or 0.0) < 0.58:
        return "", []

    cards = match_pps_qa_cards(user_message, max_cards=3)
    if not cards:
        return "", []

    q = (user_message or "").replace(" ", "").lower()
    lines = [
        "### 1. 질문의도 파악",
        "- 이 질문은 단순 조문 조회가 아니라, 기존 조달청 질의응답·실무 해석사례와 유사한 쟁점을 설명해 달라는 요청으로 분류했습니다.",
        "- 아래 사례는 실무 해석 보조자료이며, 최종 법적 결론은 적용 기관, 계약문서, 내부 법령 DB와 source map으로 다시 확인해야 합니다.",
        "",
        "### 2. 유사 해석사례 요지",
    ]
    for card in cards[:3]:
        title = str(card.get("title") or "조달청 질의응답 해석사례")
        date = f" ({card.get('date')})" if card.get("date") else ""
        excerpt = html.unescape(re.sub(r"\s+", " ", str(card.get("answer_excerpt") or "")).strip())
        excerpt = re.sub(r"^\d+\.\s*안녕하십니까\?\s*", "", excerpt)
        excerpt = re.sub(r"귀하께서 국민신문고를 통해 신청하신 민원[^.。]*[.。]\s*", "", excerpt)
        excerpt = re.sub(r"^\d+\.\s*", "", excerpt).strip()
        if len(excerpt) > 360:
            excerpt = excerpt[:360].rstrip() + "..."
        lines.append(f"- **{title}**{date}: {excerpt}")

    lines.extend(["", "### 3. 실무 검토 순서"])
    if "자동연장" in q or "계약기간" in q:
        lines.extend([
            "- 자동연장 조항은 특별한 사유 없이 반복 갱신되는 구조인지 먼저 봅니다.",
            "- 업무 공백을 막기 위한 단기간 잠정 연장인지, 사실상 경쟁절차를 회피하는 구조인지 구분합니다.",
            "- 차기 계약 절차 착수 시점, 장기계속계약 활용 가능성, 계약문서상 연장 근거를 함께 확인합니다.",
        ])
    elif "간접비" in q or "공사기간" in q or "공기연장" in q:
        lines.extend([
            "- 공사기간 연장 원인이 발주기관 사정, 불가항력, 계약상대자 책임 여부 중 어디에 해당하는지 먼저 구분합니다.",
            "- 연장 기간과 실제 추가 지출 사이의 관련성을 자료로 남깁니다.",
            "- **간접비**는 항목명만으로 자동 인정하지 말고, 숙소비·임차료·현장관리비 등 실제 발생비용과 계약조건·실비 산정자료를 함께 보아 조정 대상 여부를 검토합니다.",
            "- 지방계약 사안이면 국가계약 해석사례를 그대로 결론으로 쓰지 말고 지방계약 법령·예규 기준으로 다시 대조합니다.",
        ])
    else:
        lines.extend([
            "- 기관유형과 적용 법체계를 먼저 확정합니다.",
            "- 계약문서, 공고문, 과업지시서, 산출내역서 등 사실관계 자료를 확인합니다.",
            "- 유사 해석사례는 판단 방향을 잡는 데 쓰고, 금액·조문·기한은 최신 내부 법령 DB 기준으로 재확인합니다.",
        ])

    lines.extend([
        "",
        "### 4. 확인 필요사항",
        "- 유사 조달청 Q&A는 법적 구속력이 있는 최종 근거가 아니라 실무 해석 참고자료입니다.",
        "- 실제 처리 전에는 해당 기관의 계약담당자 판단, 계약문서, 적용 법령·행정규칙 원문을 함께 확인하세요.",
        "- 금액 기준, 조문 번호, 시행일은 매뉴얼·Q&A가 아니라 내부 법령 DB와 source map 기준을 우선합니다.",
    ])
    return "\n".join(lines), cards


def _display_amount_for_answer(amount: int | None, user_message: str) -> str:
    if amount is None:
        return "금액 미확인"
    compact = (user_message or "").replace(" ", "").replace(",", "")
    numeric = f"{amount:,}원"
    compound = re.search(
        r"(?:\d+(?:\.\d+)?억)?(?:\d+(?:\.\d+)?천)?(?:\d+(?:\.\d+)?백)?만원",
        compact,
    )
    if compound and re.search(r"\d", compound.group(0)):
        return f"{compound.group(0)}({numeric})"
    original = re.search(r"\d+(?:\.\d+)?(?:천만원|백만원|억원|억|천만|백만|만원|원)", compact)
    if original:
        return f"{original.group(0)}({numeric})"
    return numeric


def _is_practice_manual_fast_query(user_message: str) -> bool:
    """실무 매뉴얼 카드로 빠르게 답할 수 있는 설명/비교/절차형 질문인지 판별한다."""
    q = (user_message or "").replace(" ", "").lower()
    if not q:
        return False
    if _parse_amount(user_message) is not None:
        return False
    if any(term in q for term in ("업체추천", "업체후보", "업체있", "찾아", "검색")) and not (
        ("면허" in q and "공사" in q)
        or "직접생산" in q
        or "중소기업자간" in q
    ):
        return False
    explanatory_possible_question = (
        "용역" in q
        and "지역제한" in q
        and any(term in q for term in ("부산", "지역업체", "설명", "관점"))
    )
    agency_law_conflict_possible_question = (
        any(term in q for term in ("국가기관", "국가계약", "공기업", "준정부", "공공기관"))
        and any(term in q for term in ("지방계약", "지방자치단체", "지자체"))
        and any(term in q for term in (
            "그대로", "다르", "안되", "안되지", "혼동", "기준", "우대", "지역제한",
            "참고", "준용", "적용", "충돌", "비교", "차이",
        ))
    )
    if (
        not explanatory_possible_question
        and not agency_law_conflict_possible_question
        and any(term in q for term in ("가능", "되나", "될까", "해도", "할수", "계약해도"))
    ) and any(
        method in q for method in ("수의계약", "지역제한", "공동도급", "입찰", "가점")
    ):
        return False

    practice_intent = any(term in q for term in (
        "뜻", "개념", "정의", "용어", "차이", "다르게", "구분", "뭐야", "무슨말",
        "절차", "흐름", "단계", "순서", "프로세스", "쟁점", "체크", "봐야", "확인", "검토", "방법", "알려",
        "유의", "주의", "어떤계약", "어떻게검토", "어떻게", "달라", "예시", "설명",
        "정리", "한번에", "전체", "문제", "리스크", "분리발주", "분할발주", "쪼개기",
        "나눠발주", "나누어발주", "묶어발주", "기준", "공고문", "입찰공고",
    ))
    procurement_context = any(term in q for term in (
        "계약", "입찰", "수의", "견적", "물품", "용역", "공사", "유지보수",
        "종합쇼핑몰", "mas", "제3자단가", "지역제한", "공동도급", "가점",
        "공동이행", "분담이행", "공동수급", "공동계약", "제안요청서", "과업지시서",
        "중소기업자간", "직접생산", "지역상품", "구매", "제품", "공공구매", "우선구매", "구매지원", "지원제도",
        "추정가격", "예정가격", "기초금액", "추정금액", "규격서", "브랜드", "부당제한", "동등이상",
        "지체상금", "지연배상금",
    ))
    return practice_intent and procurement_context


def _build_practice_manual_fast_answer(user_message: str, agency_type: str | None) -> tuple[str, list[dict]]:
    """매뉴얼 카드 기반 설명형 답변을 만든다. 금액/법적 결론은 포함하지 않는다."""
    if not _is_practice_manual_fast_query(user_message):
        return "", []

    agency_key = _normalize_agency_type(agency_type) if agency_type else "default"
    q = (user_message or "").replace(" ", "").lower()
    item_hint = next(
        (
            term
            for term in (
                "보안용카메라", "냉난방기", "경비용역", "청소용역", "포장공사", "전기공사", "행사용역",
                "컴퓨터", "노트북", "프린터", "서버", "근무복", "단체복",
            )
            if term in (user_message or "")
        ),
        "",
    )
    is_joint_method_question = "공동이행" in q or "분담이행" in q
    contract_object = _get_router_contract_object(None, user_message)
    agency_for_cards = agency_key if agency_key != "default" else None
    is_public_purchase_question = any(term in q for term in ("공공구매", "우선구매")) and any(term in q for term in ("부산업체", "지역업체", "부산", "지역상품"))
    is_construction_material_question = any(term in q for term in ("공사용자재", "관급자재", "직접구매"))
    is_split_procurement_question = (
        any(term in q for term in ("분리발주", "분할발주", "쪼개기", "나눠발주", "나누어발주", "묶어발주"))
        and any(term in q for term in ("공사", "물품", "용역", "발주", "구매"))
    )
    is_design_print_mixed_question = "디자인" in q and "인쇄" in q and any(term in q for term in ("용역", "물품", "발주", "구매"))
    is_incidental_work_question = "부대공사" in q or ("주된공사" in q and "부대" in q)
    is_bid_notice_local_company_question = (
        any(term in q for term in ("입찰공고문", "입찰공고", "공고문"))
        and any(term in q for term in ("지역업체", "부산업체", "지역상품", "부산"))
        and any(term in q for term in ("확인", "항목", "체크", "활용", "작성", "만들"))
    )
    is_construction_license_basis_question = (
        any(term in q for term in ("전기공사", "소방공사", "정보통신공사", "공사업체"))
        and any(term in q for term in ("부산업체", "지역업체", "후보"))
        and "면허" in q
    )
    is_road_pavement_regional_strategy_question = (
        "포장공사" in q
        and any(term in q for term in ("지역제한", "공동도급", "적격심사", "지역업체"))
    )
    is_event_service_regional_question = (
        "행사용역" in q
        and any(term in q for term in ("부산업체", "지역업체", "참가자격", "발주"))
    )
    is_service_regional_restriction_question = (
        "용역" in q
        and "지역제한" in q
        and any(term in q for term in ("부산업체", "지역업체", "부산", "활용", "설명"))
    )
    is_service_local_participation_question = (
        "용역" in q
        and any(term in q for term in ("부산업체", "지역업체", "부산", "지역상품"))
        and any(term in q for term in ("참여", "활용", "방법", "가능한방법", "계약하려면", "발주하려면", "어떻게"))
    )
    is_price_terms_question = all(term in q for term in ("추정가격", "예정가격", "기초금액")) or (
        "추정금액" in q and any(term in q for term in ("차이", "구분", "뭐야"))
    )
    is_delay_penalty_question = "지체상금" in q and "지연배상금" in q
    is_specific_brand_spec_question = (
        any(term in q for term in ("특정브랜드", "특정상표", "브랜드"))
        and any(term in q for term in ("규격서", "동등", "부당제한", "노트북"))
    )
    is_private_school_subsidy_question = (
        "사립대학교" in q
        and any(term in q for term in ("국고보조금", "보조금"))
        and any(term in q for term in ("국가계약", "용역", "발주", "절차"))
    )
    is_landscape_construction_regional_question = (
        "조경공사" in q
        and any(term in q for term in ("부산업체", "부산", "지역제한", "면허"))
    )
    is_invested_institution_local_law_question = (
        any(term in q for term in ("출자출연기관", "출자·출연기관", "출연기관"))
        and any(term in q for term in ("지방계약", "지방계약법", "지역업체", "그대로"))
    )
    is_info_telecom_construction_question = (
        "정보통신공사" in q
        and any(term in q for term in ("종합공사", "전문공사", "기준", "구분"))
    )
    is_agency_law_conflict_question = (
        any(term in q for term in ("국가기관", "국가계약", "공기업", "준정부", "공공기관"))
        and any(term in q for term in ("지방계약", "지방자치단체", "지자체"))
        and any(term in q for term in (
            "그대로", "다르", "안되", "안되지", "혼동", "기준", "우대", "지역제한",
            "참고", "준용", "적용", "충돌", "비교", "차이",
        ))
    )
    is_public_corp_law_conflict_question = (
        is_agency_law_conflict_question
        and any(term in q for term in ("공기업", "준정부", "공공기관"))
        and "국가기관" not in q
    )
    is_fire_facility_construction_question = (
        ("소방시설공사" in q or ("소방" in q and "공사" in q))
        and any(term in q for term in ("전문공사", "지역제한", "기준", "면허", "공종"))
    )
    is_cloud_software_question = "클라우드" in q or "소프트웨어" in q
    is_server_mixed_question = "서버" in q and any(term in q for term in ("설치", "용역", "장비", "소프트웨어"))
    is_translation_question = "번역" in q
    special_practice_question = any((
        is_public_purchase_question,
        is_construction_material_question,
        is_split_procurement_question,
        is_design_print_mixed_question,
        is_incidental_work_question,
        is_bid_notice_local_company_question,
        is_construction_license_basis_question,
        is_road_pavement_regional_strategy_question,
        is_event_service_regional_question,
        is_service_regional_restriction_question,
        is_service_local_participation_question,
        is_price_terms_question,
        is_delay_penalty_question,
        is_specific_brand_spec_question,
        is_private_school_subsidy_question,
        is_landscape_construction_regional_question,
        is_invested_institution_local_law_question,
        is_info_telecom_construction_question,
        is_agency_law_conflict_question,
        is_fire_facility_construction_question,
        is_cloud_software_question,
        is_server_mixed_question,
        is_translation_question,
    ))
    is_lifecycle_procedure_question = (
        not special_practice_question
        and is_contract_procedure_query(user_message)
        and any(term in q for term in (
        "계약절차",
        "구매절차",
        "계약업무흐름",
        "절차를안내",
        "절차알려",
        "처음부터",
        "전체과정",
        "전체흐름",
        "흐름",
        "단계",
        "순서",
        "프로세스",
        ))
    )
    if is_lifecycle_procedure_question:
        lifecycle_cards = match_contract_lifecycle_cards(
            user_message,
            contract_object=contract_object,
            agency_type=agency_for_cards,
            max_cards=13,
        )
        if lifecycle_cards:
            sections = [
                "### 1. 질문의도 파악",
                "- 이 질문은 특정 금액의 가능/불가능 판단이 아니라, 계약 절차와 실무 확인순서를 안내해 달라는 요청으로 분류했습니다.",
                "- 절차의 뼈대는 실무 매뉴얼 카드에서 가져오고, 금액 기준·수의계약 가능 여부·지역제한 기준 같은 법적 판단 지점은 최신 법령·행정규칙 기준으로 별도 검증해야 합니다.",
                "",
                render_contract_lifecycle_for_answer(
                    lifecycle_cards,
                    contract_object=contract_object,
                    max_cards=13,
                ),
                "",
                "### 4. 다음 단계",
                "- 실제 사안에서는 금액, 기관유형, 세부품명·과업범위·공종을 확정한 뒤 계약방법 판단 카드와 법령 근거카드를 붙여야 합니다.",
                "- 지역상품 구매를 확대하려면 절차 중 `계약방법 결정`, `규격·과업·참가자격 설계`, `낙찰자 결정`, `검사·검수` 단계에서 지역업체 보호제도를 연결하는 방식이 좋습니다.",
            ]
            return "\n".join(sections), lifecycle_cards

    cards = match_practice_manual_cards(
        user_message,
        contract_object=None,
        agency_type=agency_key,
        max_cards=4,
    )
    if is_joint_method_question:
        cards = [
            card for card in cards
            if "공동" in str(card.get("title") or "")
            or any("공동" in str(keyword) for keyword in (card.get("keywords") or []))
        ][:3]
    if not cards and not is_joint_method_question and not special_practice_question:
        return "", []

    sections = [
        "### 1. 질문의도 파악",
        "- 이 질문은 특정 금액의 계약 가능 여부 판단이 아니라, 계약 유형·절차·실무 쟁점을 설명해 달라는 요청으로 분류했습니다.",
    ]

    if "중소기업자간" in q or "직접생산" in q:
        subject = f"**{item_hint}** 같은 " if item_hint else ""
        sections.extend([
            "",
            "### 2. 중소기업자간 경쟁제품과 직접생산확인",
            f"- {subject}중소기업자간 경쟁제품은 해당 품목을 중소기업자 간 경쟁으로 구매하도록 관리하는 품목군입니다.",
            "- 이 품목을 구매할 때는 단순히 중소기업인지뿐 아니라, 해당 업체가 그 세부품명에 대해 **직접생산확인증명서**를 갖고 있는지 확인해야 합니다.",
            "- 실무 확인은 공공구매종합정보망(SMPP) 또는 관련 증명서로 세부품명, 유효기간, 업체명, 사업자번호, 직접생산 확인 범위가 구매하려는 규격과 맞는지 대조하는 방식으로 진행합니다.",
            "- 지역상품 구매지원 관점에서는 부산 업체 후보를 찾더라도 직접생산확인 대상 품목이면 부산 소재 여부보다 직접생산 확인과 세부품명 일치가 먼저입니다.",
        ])
    elif "지역상품" in q and any(term in q for term in ("구매지원", "지원제도", "정리", "한번에", "전체")):
        sections.extend([
            "",
            "### 2. 지역상품 구매지원 제도 묶음",
            "- **지역제한경쟁입찰**: 법령상 금액·계약대상 요건이 맞을 때 입찰참가 지역을 제한해 지역업체 참여를 확보하는 장치입니다.",
            "- **지역의무공동도급**: 주로 공사에서 공동수급체 안에 지역업체 참여비율을 두어 지역업체 시공 참여를 확보하는 장치입니다.",
            "- **지역업체 참여도·가점**: 용역·공사 등 평가방식에 따라 지역업체 참여비율이나 지역업체 참여도를 평가항목으로 반영하는 방식입니다.",
            "- **종합쇼핑몰/MAS·제3자단가**: 부산 업체가 등록된 품목이면 납품요구, 2단계 경쟁, 현장지원·A/S 같은 정당한 평가요소로 지역상품 활용 가능성을 검토합니다.",
            "- **정책기업·기술개발제품·우수조달·혁신제품**: 여성기업, 장애인기업, 사회적기업, 기술개발제품 등은 별도 우대·수의계약·우선구매 경로와 연결될 수 있으므로 인증·지정·유효상태를 확인합니다.",
            "- **중소기업자간 경쟁제품·직접생산확인**: 해당 품목이면 부산업체 후보라도 직접생산확인과 세부품명 일치 여부가 우선 확인사항입니다.",
        ])
    elif is_public_purchase_question:
        sections.extend([
            "",
            "### 2. 공공구매·우선구매 제도와 부산업체 연결",
            "- **공공구매 우선구매**는 특정 업체를 바로 지정하는 장치가 아니라, 법령·제도상 우선구매 대상 제품인지 확인하고 구매전략에 반영하는 실무 검토 축입니다.",
            "- 먼저 품목이 **중소기업자간 경쟁제품**인지, **직접생산확인** 대상인지 확인합니다. 해당되면 부산업체 후보도 세부품명과 직접생산확인 범위가 맞아야 합니다.",
            "- 다음으로 **기술개발제품, 우수조달물품, 혁신제품, 녹색제품, 창업기업제품, 장애인기업·여성기업·사회적기업 제품** 등 우선구매·수의계약·가점과 연결될 수 있는 지위를 확인합니다.",
            "- 종합쇼핑몰/MAS 등록 품목이면 납품요구, 2단계 경쟁, 납품 가능 지역, A/S·현장지원 같은 정당한 평가요소로 부산업체 활용 가능성을 검토합니다.",
            "- 답변이나 공고문에는 `부산업체라서 가능`이 아니라 `제도 요건, 품목 적합성, 조달등록, 인증·지정 상태, 경쟁성`을 근거로 남기는 방식이 안전합니다.",
        ])
    elif is_construction_material_question:
        sections.extend([
            "",
            "### 2. 공사용자재 직접구매·관급자재 검토",
            "- 공사에 포함되는 자재라도 일정 품목은 **공사용자재 직접구매** 또는 관급자재 구매로 따로 검토해야 할 수 있습니다.",
            "- 먼저 공종과 자재의 세부품명, 직접구매 대상 여부, 중소기업자간 경쟁제품 해당 여부, 직접생산확인 필요 여부를 확인합니다.",
            "- 관급자재로 분리할 경우 공사 시공범위, 납품·설치 책임, 하자책임, 공정 지연 위험, 검사·검수 주체를 공사계약 조건과 맞춰야 합니다.",
            "- 정보통신공사·전기공사·소방공사처럼 면허와 자재가 함께 얽히는 사안은 공사계약, 물품구매, 직접구매 대상 품목을 동시에 비교해야 합니다.",
        ])
    elif is_split_procurement_question:
        sections.extend([
            "",
            "### 2. 분리발주·쪼개기 발주 위험 검토",
            "- **공사**와 **물품** 또는 용역을 나눠 발주할 때는 정당한 **분리발주**인지, 금액 기준이나 경쟁 절차를 피하려는 **쪼개기 발주**로 보일 수 있는지 먼저 구분합니다.",
            "- 분리발주가 필요한 경우에는 공사 범위, 관급자재·물품 납품 범위, 설치 책임, 하자책임, 검사·검수 주체, 공정 간섭 위험을 문서로 남깁니다.",
            "- 같은 목적·같은 시기·같은 부서의 수요를 인위적으로 나누면 분할발주 또는 쪼개기 수의계약 지적을 받을 수 있으므로, 수요 취합과 추정가격 산정 근거를 보관해야 합니다.",
            "- 지역업체 활용 목적이 있더라도 분리 자체의 필요성, 경쟁성 확보 방식, 특정업체 유리 조건 배제 여부를 함께 설명하는 편이 안전합니다.",
        ])
    elif is_design_print_mixed_question:
        sections.extend([
            "",
            "### 2. 디자인·인쇄 혼합 사업의 계약대상 구분",
            "- **디자인** 기획, 편집, 저작권 처리, 수정·검수, 결과물 제작관리가 중심이면 용역 성격이 강합니다.",
            "- **인쇄** 물량, 규격, 납품, 검수, 종이·후가공 사양이 중심이면 물품 제조·구매 성격을 함께 봐야 합니다.",
            "- 하나로 발주할 때는 디자인 산출물과 인쇄 납품물의 책임, 저작권·원본파일 제공, 교정 횟수, 납품기한, 검사·검수 기준을 과업지시서와 규격서에 나눠 적습니다.",
            "- 지역업체 활용은 특정 업체 지정보다 디자인 수행능력, 인쇄 설비·납기, 현장 대응, 유사실적 같은 객관적 평가요소로 연결하는 편이 안전합니다.",
        ])
    elif is_incidental_work_question:
        sections.extend([
            "",
            "### 2. 부대공사 판단자료",
            "- **부대공사**로 묶을 수 있는지는 주된 공사와의 목적·장소·공정·기능상 연계성을 자료로 확인해야 합니다.",
            "- 설계서, 시방서, 내역서, 공종별 금액, 면허·업종 요건, 현장 여건, 분리 시 공정 간섭이나 하자책임 문제가 생기는지를 함께 봅니다.",
            "- 부대공사라는 이유로 별도 면허나 분리발주 필요성을 생략하면 부당제한·무면허 시공 논란이 생길 수 있으므로, 주된 공사와 부대 범위를 문서화합니다.",
            "- 금액 기준이나 법령상 허용 범위는 최신 법령·행정규칙 기준으로 별도로 검증해야 합니다.",
        ])
    elif is_bid_notice_local_company_question:
        sections.extend([
            "",
            "### 2. 입찰공고문 지역업체 활용 체크리스트",
            "- **입찰공고문**에는 지역업체 활용 취지보다 먼저 계약유형, 추정가격, 참가자격, 낙찰자 결정방법, 평가항목의 근거를 분리해 적어야 합니다.",
            "- **지역업체** 또는 부산업체 관련 조건은 지역제한, 지역의무공동도급, 지역업체 참여도·가점, 현장 대응성, 납품·A/S 조건 중 어떤 제도에 근거하는지 구분합니다.",
            "- 금액 기준, 비율, 점수, 적용 대상은 공고문 문안에 바로 쓰기 전에 최신 법령·고시 기준으로 확인합니다.",
            "- 특정 부산업체만 맞출 수 있는 규격·실적·인력·장비 조건은 부당제한 리스크가 있으므로, 시장조사 자료와 경쟁 가능한 업체 수를 함께 남깁니다.",
            "- 물품은 종합쇼핑몰/MAS, 중소기업자간 경쟁제품, 직접생산확인, 인증제품 여부를 공고·제안요청 조건과 충돌하지 않게 확인합니다.",
        ])
    elif is_construction_license_basis_question:
        sections.extend([
            "",
            "### 2. 공사업체 후보는 면허 기준으로 확인",
            "- **전기공사** 같은 공사업체 후보는 제품명이 아니라 해당 공종의 **면허·업종 등록** 기준으로 먼저 찾아야 합니다.",
            "- 부산업체 후보를 볼 때도 본점 소재지, 전기공사업 등록 여부, 면허 유효성, 시공 가능 범위, 실적·기술인력, 하도급 제한 여부를 확인합니다.",
            "- 물품 구매처럼 종합쇼핑몰 상품명만으로 판단하면 안 되고, 공사계약의 참가자격과 면허 요건을 공고문에 객관적으로 적어야 합니다.",
            "- 금액 기준, 지역제한, 공동도급, 적격심사 적용 여부는 최신 법령·행정규칙 기준으로 별도 검증합니다.",
        ])
    elif is_road_pavement_regional_strategy_question:
        sections.extend([
            "",
            "### 2. 포장공사 지역업체 참여 전략",
            "- **도로 포장공사**는 공종·면허와 추정가격을 먼저 확인한 뒤, 지역제한, 공동도급, 적격심사를 순서대로 연결합니다.",
            "- 지역제한은 입찰참가자격 단계에서 부산 등 지역 범위를 제한할 수 있는지 보는 장치이고, 금액·공종 기준은 최신 법령·고시 기준으로 확인해야 합니다.",
            "- **공동도급**은 지역업체가 공동수급체 구성원으로 참여할 수 있는지, 지분율·분담범위·시공능력을 확인하는 장치입니다.",
            "- 적격심사나 평가 단계에서는 지역업체 참여도, 시공경험, 기술능력, 신인도 항목을 공고문·평가기준과 맞춰야 합니다.",
        ])
    elif is_event_service_regional_question:
        sections.extend([
            "",
            "### 2. 행사용역 참가자격 설계",
            "- **행사용역**을 부산업체 중심으로 검토하더라도 참가자격은 과업 수행에 필요한 범위에서 객관적으로 설계해야 합니다.",
            "- 부산업체 활용은 지역제한 가능성, 현장 대응성, 유사 행사 수행경험, 안전관리, 장비·인력 투입계획, 긴급 대응체계 같은 정당한 요소로 연결합니다.",
            "- 특정 업체만 충족할 수 있는 과도한 실적, 특정 장소·거래처 경험, 불필요한 장비 보유 조건은 부당제한 리스크가 큽니다.",
            "- 제안평가를 쓰는 경우 지역업체 여부 자체보다 수행계획, 현장 운영능력, 지역 이해도, 안전·민원 대응을 평가항목으로 정리하는 편이 안전합니다.",
        ])
    elif is_service_regional_restriction_question or is_service_local_participation_question:
        service_subject = item_hint or "용역"
        sections.extend([
            "",
            f"### 2. {service_subject}에서 지역업체 참여를 늘리는 검토 경로",
            f"- **{service_subject}**은 과업 성격, 면허·등록 요건, 수행 장소, 현장 대응 필요성을 먼저 확정한 뒤 지역업체 참여 방식을 설계합니다.",
            "- **지역제한경쟁입찰**: 계약유형, 추정가격, 과업 성격, 부산 지역 내 경쟁 가능한 업체 수를 확인한 뒤 검토합니다. 공사 기준을 그대로 가져오면 안 됩니다.",
            "- **지역업체 참여도·가점**: 적격심사, 협상계약, 제안평가 등 평가방식에서 지역업체 참여도, 현장 대응성, 지역 내 수행체계 같은 객관적 항목으로 연결할 수 있는지 봅니다.",
            "- **공동수급 허용**: 단독 수행이 어렵거나 전문 분야가 섞인 용역이면 공동이행·분담이행을 허용해 부산업체가 구성원으로 참여할 여지를 검토합니다.",
            "- **수의계약·견적 방식**: 금액, 수의계약 사유, 정책기업 여부가 맞는 경우에만 검토합니다. 지역업체라는 이유만으로 바로 수의계약 결론을 내리면 안 됩니다.",
            "- **참가자격·과업 설계**: 면허·등록, 실적, 인력, 장비, 현장 대응 요건은 과업 수행에 필요한 범위로 쓰고 특정 업체만 유리한 조건은 피해야 합니다.",
            "- 확인할 근거 축은 지방계약법 시행령 제20조·제25조·제30조, 지방계약법 시행규칙 제24조, 지방자치단체 입찰 및 계약집행기준, 지방자치단체 입찰시 낙찰자 결정기준입니다.",
        ])
    elif is_price_terms_question:
        sections.extend([
            "",
            "### 2. 가격 용어 구분",
            "- **추정가격**은 계약방법, 국제입찰, 지역제한, 수의계약 기준 등을 판단할 때 쓰는 기준 금액입니다.",
            "- **예정가격**은 입찰·계약에서 낙찰자 결정과 계약금액 산정의 기준이 되는 가격입니다.",
            "- **기초금액**은 예정가격 작성을 위해 공개하거나 산정하는 기초 자료 성격의 금액입니다.",
            "- **추정금액**은 공사 등에서 추정가격에 관급자재 등 관련 금액을 더해 사업 규모를 볼 때 쓰이는 경우가 많습니다.",
            "- 실무에서는 어떤 금액을 기준으로 법령 한도를 판단하는지 혼동하면 안 되므로, 금액 기준은 최신 법령·고시 기준으로 용어별 확인합니다.",
        ])
    elif is_delay_penalty_question:
        sections.extend([
            "",
            "### 2. 지체상금과 지연배상금 설명",
            "- **지체상금**은 실무에서 오래 쓰인 표현이고, **지연배상금**은 계약 이행 지연에 대해 계약상대자가 부담하는 배상 성격의 금액을 설명할 때 쓰는 표현입니다.",
            "- 실무 안내에서는 `지연배상금(실무상 지체상금이라고 부르는 경우가 있음)`처럼 병기하면 혼동을 줄일 수 있습니다.",
            "- 핵심은 명칭보다 지체 사유, 귀책 여부, 지체일수 산정, 계약서상 약정, 감액·면제 사유를 확인하는 것입니다.",
            "- 배상금률, 한도, 제외일수 같은 숫자 기준은 최신 법령·행정규칙 기준으로 별도 확인해야 합니다.",
        ])
    elif is_specific_brand_spec_question:
        sections.extend([
            "",
            "### 2. 특정 브랜드·동등 이상 규격서 작성",
            "- 노트북 같은 물품 규격서에 **특정 브랜드**나 특정 모델만 사실상 충족할 수 있는 조건을 쓰면 **부당제한** 문제가 생길 수 있습니다.",
            "- 필요한 성능은 CPU, 메모리, 저장장치, 화면, 보안, A/S, 호환성처럼 객관적 기준으로 쓰고, 특정 상표가 필요하면 예외 사유를 문서화해야 합니다.",
            "- `동등 이상` 표현을 쓸 때도 비교 가능한 성능·규격·인증 기준을 함께 적어야 하며, 특정 제조사 고유 기능만 요구하지 않도록 점검합니다.",
            "- 시장조사 자료, 복수 제품 비교표, 업무 필요성, 예산 산출근거를 감사 대응 자료로 남기는 편이 안전합니다.",
        ])
    elif is_private_school_subsidy_question:
        sections.extend([
            "",
            "### 2. 사립대학교 국고보조금 발주 확인",
            "- **사립대학교**가 **국고보조금**으로 용역을 발주한다고 해서 곧바로 모든 절차가 국가계약법으로 자동 전환된다고 단정하면 안 됩니다.",
            "- 먼저 보조금 교부조건, 위탁·대행 여부, 보조사업 정산지침, 대학 자체 계약규정, 사업 주관기관 지침을 함께 확인합니다.",
            "- 교부조건이나 사업지침에서 **국가계약법** 또는 조달 절차 준용을 요구하는지, 자체 규정을 우선하는지 문서로 남겨야 합니다.",
            "- 공고문에는 적용 규정, 예산 재원, 정산·검사 기준, 이해충돌·특혜 방지 기준을 분명히 적는 편이 안전합니다.",
        ])
    elif is_landscape_construction_regional_question:
        sections.extend([
            "",
            "### 2. 조경공사 지역제한·면허 설계",
            "- **조경공사**를 부산업체 중심으로 발주하려면 먼저 공종과 면허·업종 요건을 확정합니다.",
            "- 지역제한은 추정가격, 공사 종류, 본점 소재지, 부산 지역 내 경쟁 가능한 업체 수를 최신 법령·고시 기준으로 확인한 뒤 공고문에 반영합니다.",
            "- 면허요건은 공사 목적 달성에 필요한 범위로 제한하고, 불필요하게 높은 실적·장비·인력 조건을 붙이면 부당제한 문제가 생길 수 있습니다.",
            "- 부산업체 활용 목적은 지역제한, 공동도급, 적격심사 평가요소 등 법령상 허용되는 장치와 연결해 문서화합니다.",
        ])
    elif is_invested_institution_local_law_question:
        sections.extend([
            "",
            "### 2. 출자·출연기관의 지방계약법 적용 확인",
            "- 부산 **출자출연기관**은 지방자치단체 본청과 같은 방식으로 **지방계약법**을 그대로 적용한다고 단정하지 말고, 설립 근거와 자체 계약규정을 먼저 봐야 합니다.",
            "- 지방계약법령 준용 조항, 조례·정관·내부 계약규정, 위탁사업 또는 보조사업 조건이 있는지 확인합니다.",
            "- 지역업체 활용은 기관 자체 규정에서 허용하는 지역제한, 평가항목, 수의계약 사유, 종합쇼핑몰/MAS 이용 가능성을 구분해 검토합니다.",
            "- 답변이나 검토서에는 `지방계약법 그대로 적용`이 아니라 `준용 여부와 내부규정 확인 후 적용`으로 남기는 편이 안전합니다.",
        ])
    elif is_info_telecom_construction_question:
        sections.extend([
            "",
            "### 2. 정보통신공사 공종 기준 구분",
            "- **정보통신공사**는 건설산업기본법상 종합공사·전문공사 구분과 별도로, 정보통신공사업 관련 면허·업종 기준을 먼저 확인해야 합니다.",
            "- 종합공사·전문공사 금액 기준을 기계적으로 적용하기 전에 해당 공사가 정보통신공사업 범위인지, 다른 공종과 분리해야 하는지 봅니다.",
            "- 발주 시에는 공종, 면허, 설계·시방, 관급자재, 하자책임, 분리발주 필요성을 함께 정리합니다.",
            "- 지역제한이나 수의계약 금액 기준은 최신 법령·행정규칙 기준으로 별도 검증해야 합니다.",
        ])
    elif is_public_corp_law_conflict_question:
        sections = [
            "### 1. 최우선 판단 지표: 기관 유형",
            "- **공기업**이라고만 쓰면 부족합니다. 먼저 그 기관이 **공공기관운영법상 공기업·준정부기관**인지, **지방공기업법상 지방공기업**인지부터 확정해야 합니다.",
            "",
            "| 기관 구분 | 예시 | 우선 확인 법체계 | 부산업체 우대 판단 기준 |",
            "|---|---|---|---|",
            "| 국가 공기업·준정부기관 | 한국남부발전, 부산항만공사 등 | 공공기관운영법 → 공기업·준정부기관 계약사무규칙 → 기관 자체 계약규정 → 준용 국가계약법령 | 지방계약법 지역제한 기준을 그대로 적용하지 말고, 계약사무규칙과 국가계약법령 범위에서 지역제한·공동계약·평가항목 가능성을 봅니다. |",
            "| 지방공기업 | 부산도시공사, 부산교통공사 등 | 지방공기업법 → 지방공기업법 시행령 → 기관 계약규정 → 준용 지방계약법령 | 지방공기업법령이 지방계약법령을 준용하는 범위와 기관 계약규정에 따라 지역제한·지역업체 참여도·수의계약 가능성을 봅니다. |",
            "",
            "### 2. 법령별 적용 로직",
            "- **국가 공기업·준정부기관**: 「공기업·준정부기관 계약사무규칙」 제2조는 다른 법령에 특별한 규정이 없으면 이 규칙을 따르고, 규칙에 없는 사항은 국가계약법령을 준용하도록 봅니다. 따라서 우선순위는 `공공기관운영법 → 계약사무규칙 → 자체 계약규정 → 국가계약법령`입니다.",
            "- **지방공기업**: 「지방공기업법」 제64조의2 및 같은 법 시행령 제57조의8 체계에서 계약 기준·절차와 입찰참가자격 제한 등에 관해 지방계약법령을 성질에 반하지 않는 범위에서 준용합니다. 따라서 우선순위는 `지방공기업법 → 시행령 → 기관 계약규정 → 준용 지방계약법령`입니다.",
            "- 지역제한 가능 금액은 기관유형, 계약대상(물품·용역·공사), 국제입찰 여부, 고시금액에 따라 달라지므로 답변에 고정 숫자를 박지 말고 최신 법령·고시 기준으로 확인해야 합니다.",
            "",
            "### 3. 실무 검토 순서",
            "- **1단계: 기관 성격 확인**: 기재부 지정 공기업·준정부기관인지, 부산시 등 지방자치단체가 설립한 지방공기업인지 확인합니다.",
            "- **2단계: 계약대상과 금액 확인**: 물품·용역·공사 중 무엇인지, 추정가격 기준인지, 지역제한 가능 구간인지 확인합니다.",
            "- **3단계: 구매경로 확인**: 자체 입찰이면 지역제한·공동계약·평가항목 근거를 보고, 종합쇼핑몰/MAS이면 MAS 2단계경쟁 기준과 지역업체 평가항목을 따로 봅니다.",
            "- **4단계: 부산업체 연결**: 법령상 허용되는 경로 안에서 부산 소재 조달등록 업체, 중소기업자간 경쟁제품·직접생산확인 업체, 기술개발제품·혁신제품 보유 업체를 후보로 붙여 검토합니다.",
            "",
            "### 4. 결론",
            "- 질문의 답은 **먼저 공기업·준정부기관 계약사무규칙을 보되, 그 기관이 지방공기업이면 지방공기업법 체계로 전환해야 한다**입니다.",
            "- 국가 공기업·준정부기관이 지방계약법 지역제한 기준을 그대로 적용하거나, 지방공기업이 국가계약법 기준으로만 판단하면 부당한 입찰참가자격 제한 또는 감사 리스크가 생길 수 있습니다.",
        ]
        return "\n".join(sections), cards
    elif is_agency_law_conflict_question:
        try:
            from policies.numeric_basis_policy import get_numeric_display
        except ImportError:
            from importlib import import_module

            get_numeric_display = import_module("app.policies.numeric_basis_policy").get_numeric_display

        national_goods_service = get_numeric_display("P_NATIONAL_LIMITED_BID_GOODS_SERVICE_THRESHOLD") or "국가계약법 제4조 고시금액 확인 필요"
        national_general = get_numeric_display("P_NATIONAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD") or "국가계약법 제4조 고시금액 확인 필요"
        national_specialty = get_numeric_display("P_NATIONAL_LIMITED_BID_SPECIALTY_CONSTRUCTION_THRESHOLD") or "국가계약법 시행규칙 제24조 금액 확인 필요"
        local_general = get_numeric_display("P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD") or "지방계약법 시행규칙 제24조 금액 확인 필요"
        local_specialty = get_numeric_display("P_LOCAL_LIMITED_BID_SPECIALTY_CONSTRUCTION_THRESHOLD") or "지방계약법 시행규칙 제24조 금액 확인 필요"
        local_technical_service = get_numeric_display("P_LOCAL_LIMITED_BID_TECHNICAL_SERVICE_THRESHOLD") or "지방계약법 시행규칙 제24조 금액 확인 필요"
        local_safety_service = get_numeric_display("P_LOCAL_LIMITED_BID_SAFETY_DIAGNOSIS_SERVICE_THRESHOLD") or "지방계약법 시행규칙 제24조 금액 확인 필요"
        local_busan_gu_gun = get_numeric_display("P_LOCAL_LIMITED_BID_SEOUL_BUSAN_INCHEON_GU_GUN_THRESHOLD") or "지방계약법 시행규칙 제24조 금액 확인 필요"

        sections = [
            "### 1. 결론: 비교는 가능하지만 적용 근거로 쓰면 안 됩니다",
            "- 국가기관은 지역제한경쟁입찰을 설계할 때 **국가계약법 제4조, 국가계약법 시행령 제21조, 국가계약법 시행규칙 제24조**를 우선 적용해야 합니다.",
            "- 지방계약법의 부산 지역제한 기준은 내부 비교자료로 참고할 수는 있지만, 국가기관 공고문의 법적 근거로 그대로 쓰면 안 됩니다.",
            "- 지방계약 기준으로 더 넓은 부산 지역제한을 걸면 **부당한 입찰참가자격 제한**, 감사 지적, 입찰취소·무효 또는 탈락업체 분쟁 리스크가 생깁니다.",
            "",
            "### 2. 법체계 충돌 포인트",
            "| 구분 | 국가기관 | 지방자치단체 | 충돌 포인트 |",
            "|---|---|---|---|",
            "| 적용 법령 | 국가계약법령 | 지방계약법령 | 발주기관 유형이 달라 서로 준용할 수 없습니다. |",
            "| 지역제한 근거 | 국가계약법 시행령 제21조 및 시행규칙 제24조 | 지방계약법 시행령 제20조 및 시행규칙 제24조 | 조문, 위임 고시, 금액 체계가 다릅니다. |",
            "| 본점 소재지 제한 | 국가계약법령상 허용 범위 안에서만 가능 | 지방계약법령상 허용 범위 안에서 가능 | 같은 `부산 제한` 문구라도 근거 법령이 다르면 위법 판단이 달라집니다. |",
            "",
            "### 3. 계약대상별 기준 충돌 비교",
            "| 계약대상 | 국가계약 기준 | 지방계약 기준 | 실무상 충돌 |",
            "|---|---|---|---|",
            f"| 물품·일반용역 | 국가계약법 제4조 고시금액 미만({national_goods_service}) | 행정안전부장관 고시금액 미만. 부산 관할 군·구 등은 {local_busan_gu_gun} 기준이 별도로 보입니다. | 국가기관이 지방의 더 넓은 금액 기준을 가져와 부산 제한을 걸면 부당제한 소지가 큽니다. |",
            f"| 건설기술·설계·엔지니어링 등 용역 | 국가계약법 제4조 고시금액 미만({national_goods_service}) | 건설기술·건축설계·엔지니어링 용역은 {local_technical_service}, 안전점검·정밀안전진단 용역은 {local_safety_service} | 용역은 공사 기준을 가져오면 안 되고, 국가·지방의 위임 고시와 세부 용역 구분을 따로 봐야 합니다. |",
            f"| 종합공사 | {national_general} 미만 | {local_general} 미만 | 차이가 가장 커서 지방 기준을 국가기관에 적용하면 즉시 감사 리스크가 커집니다. |",
            f"| 전문공사 및 그 밖의 공사 | {national_specialty} 미만 | {local_specialty} 미만 | 숫자가 같아 보이는 구간도 공고문 근거는 국가계약법령으로 써야 합니다. |",
            "",
            "### 4. 국가기관이 부산업체를 합법적으로 고려하는 방법",
            "- **지역제한경쟁입찰**: 추정가격과 계약대상이 국가계약법 시행규칙 제24조 범위 안에 있을 때만 부산 본점 소재지 제한을 검토합니다.",
            "- **공동계약·지역업체 참여**: 금액이 지역제한 범위를 넘는 경우에는 지역제한 대신 공동수급 허용, 수행체계, 현장 대응성 등 국가계약 체계에서 허용되는 장치를 검토합니다.",
            "- **종합쇼핑몰/MAS**: MAS·제3자단가 구매라면 지역제한 공고가 아니라 납품 가능 지역, A/S, 현장지원, MAS 2단계경쟁 평가항목 등 조달청 기준 안에서 부산업체 활용 가능성을 봅니다.",
            "- **규격·평가항목 설계**: `부산업체라서 우대`가 아니라 납기, 유지보수, 현장 대응, 지역 내 서비스망처럼 계약 이행과 직접 관련된 객관 요소로 정리해야 합니다.",
            "- **업체 후보 추천 제외**: 이 질문은 품목·규격·금액이 없는 법체계 비교 질문이므로 특정 부산업체 후보를 추천하지 않습니다. 후속 질문에서 구매 품목과 금액이 제시될 때만, 법적으로 가능한 경로 안에서 부산 조달등록 업체, 직접생산확인 업체, 기술개발·혁신제품 보유 업체 후보를 붙여 검토합니다.",
            "",
            "### 5. 최종 판단",
            "- 국가기관은 지방계약법의 부산 지역제한 기준을 **비교표나 내부 검토자료로 참고**할 수는 있습니다.",
            "- 하지만 실제 입찰공고, 참가자격, 낙찰자 결정 기준에는 반드시 **국가계약법령상 지역제한 가능 금액과 제한 근거**를 써야 합니다.",
            "- 따라서 질문의 핵심 답은 `지방계약 기준을 참고는 하되, 적용은 국가계약 기준으로만 한다`입니다.",
        ]
        return "\n".join(sections), cards
    elif is_fire_facility_construction_question:
        sections.extend([
            "",
            "### 2. 소방시설공사 기준 확인 순서",
            "- **소방시설공사**는 공사계약 안에서도 공종, 면허, 분리발주 여부, 전문공사 해당 여부를 먼저 확인해야 합니다.",
            "- **전문공사 기준**은 공사의 세부 공종과 적용 업종을 나눈 뒤, 해당 면허·등록 요건과 추정가격 기준을 최신 법령·고시 기준으로 대조합니다.",
            "- **지역제한 기준**은 기관유형, 공사 종류, 추정가격, 본점 소재지, 지역 내 경쟁 가능한 업체 수를 함께 봐야 합니다.",
            "- 지역업체 활용은 `부산업체 지정`이 아니라 지역제한 가능성, 공동도급, 적격심사 평가요소, 면허 충족 여부를 문서화하는 방식으로 설계합니다.",
        ])
    elif "입찰참가자격" in q and any(term in q for term in ("좁", "부당", "제한", "특혜", "예시")):
        sections.extend([
            "",
            "### 2. 입찰참가자격 제한과 부당제한",
            "- 입찰참가자격은 계약 목적 달성에 필요한 범위 안에서 객관적으로 정해야 합니다.",
            "- 특정 업체만 충족할 수 있는 실적, 특정 상표·모델, 불필요하게 높은 면허·인력·장비 요건을 두면 **부당제한** 문제가 생길 수 있습니다.",
            "- 예를 들어 단순 납품인데 특정 지역 실적만 요구하거나, 동등 성능 제품을 배제하고 특정 제조사 규격만 요구하거나, 계약 규모에 비해 과도한 최근 실적을 요구하는 방식은 감사 리스크가 큽니다.",
            "- 지역업체 활용은 가능하지만, `부산업체만 가능`처럼 근거 없는 제한보다 지역제한, 지역업체 참여도, 현장 대응성, 납기·A/S 등 정당한 평가요소로 설계해야 합니다.",
        ])
    elif is_joint_method_question:
        sections.extend([
            "",
            "### 2. 공동이행방식과 분담이행방식의 차이",
            "- **공동이행방식**은 공동수급체 구성원이 같은 계약목적물을 함께 이행하고, 지분율에 따라 책임과 실적을 나누는 방식입니다.",
            "- **분담이행방식**은 구성원별로 맡는 공종·분야·과업을 나누어 각자 담당 부분을 이행하는 방식입니다.",
            "- 실무상 공동이행은 구성원 간 공동 책임과 지분율 관리가 중요하고, 분담이행은 분담 범위, 면허·자격, 책임 경계가 명확해야 합니다.",
            "- 지역업체 보호제도와 연결할 때는 공동수급체 구성 가능성, 지역업체 지분율·분담범위, 공고문상 허용 방식부터 확인해야 합니다.",
        ])
    elif "제안요청서" in q and "과업지시서" in q:
        sections.extend([
            "",
            "### 2. 제안요청서와 과업지시서의 차이",
            "- **제안요청서(RFP)**는 협상계약 등에서 제안자가 어떤 내용으로 제안서를 제출해야 하는지, 평가항목·배점·제출서류·제안 조건을 안내하는 문서입니다.",
            "- **과업지시서**는 계약상 수행해야 할 업무 범위, 산출물, 일정, 인력, 검사·검수 기준을 정하는 과업 수행 기준 문서입니다.",
            "- 쉽게 말하면 제안요청서는 `어떻게 제안받고 평가할지`, 과업지시서는 `계약 후 무엇을 수행하게 할지`에 더 가깝습니다.",
            "- 두 문서의 내용이 서로 충돌하면 계약 이행과 분쟁 리스크가 커지므로, 과업 범위·평가기준·성과물·검수조건을 맞춰야 합니다.",
        ])
    elif is_cloud_software_question:
        sections.extend([
            "",
            "### 2. 클라우드·소프트웨어 구매의 계약대상 구분",
            "- 클라우드 서비스 구독은 단순 물품 납품보다 **서비스 이용권·운영지원·보안·장애 대응** 요소가 커서 용역 또는 소프트웨어 구매 성격을 함께 봐야 합니다.",
            "- 상용소프트웨어 라이선스 구매라면 조달등록, 디지털서비스몰·종합쇼핑몰, 제3자단가계약, 유지보수 포함 여부를 확인합니다.",
            "- 구축·설치·운영지원이 함께 있으면 과업지시서, SLA, 보안 요구사항, 데이터 이전·반환, 저작권·사용권 범위를 계약조건에 분리해 적어야 합니다.",
            "- 금액과 계약방법 판단은 기관유형, 조달 등록 경로, 소프트웨어 사업 관련 규정, 수의계약 사유를 별도로 확인한 뒤 확정해야 합니다.",
        ])
    elif is_server_mixed_question:
        sections.extend([
            "",
            "### 2. 서버 장비와 설치·구축 용역이 섞인 경우",
            "- 서버 장비 자체는 물품 구매 성격이 강하지만, 설치·이전·환경설정·보안설정·유지보수가 포함되면 용역 요소가 함께 생깁니다.",
            "- 먼저 주된 계약목적이 장비 납품인지, 시스템 구축·운영지원인지 구분하고, 규격서와 과업지시서를 서로 충돌하지 않게 나눕니다.",
            "- 종합쇼핑몰/MAS 등록 장비인지, 소프트웨어 라이선스가 포함되는지, 기술지원확약서나 특정 제조사 조건이 부당제한이 되는지 확인해야 합니다.",
            "- 부산업체 활용은 조달등록, 납품 가능 지역, 설치·A/S 수행능력, 기술지원 체계 같은 객관적 조건으로 연결하는 편이 안전합니다.",
        ])
    elif is_translation_question:
        sections.extend([
            "",
            "### 2. 번역 용역의 계약방법 검토",
            "- 번역은 일반적으로 용역 성격이 강하므로 과업 범위, 언어쌍, 분량, 납기, 검수 기준, 보안·비밀유지 조건을 먼저 정리합니다.",
            "- 수의계약이나 2인 이상 견적을 검토할 때는 추정가격, 견적 방식, 참가자격 제한 필요성, 수행실적 요구의 적정성을 분리해 봐야 합니다.",
            "- 특정 번역사나 특정 실적만 요구하면 부당제한 문제가 생길 수 있으므로, 필요한 경우 전문분야 경험·품질관리 방식·보안서약 등 객관적 요건으로 설계합니다.",
            "- 지역업체를 고려하더라도 번역 품질과 과업수행 가능성을 중심으로 평가하고, 금액 기준은 최신 법령·행정규칙 기준으로 별도 확인해야 합니다.",
        ])
    elif "용역" in q and any(term in q for term in ("물품", "구매", "제품")):
        sections.extend([
            "",
            "### 2. 물품 구매와 용역계약의 핵심 차이",
            "- **물품 구매**는 규격, 납품 가능 여부, 조달등록·종합쇼핑몰/MAS, 직접생산·인증·검수 조건을 먼저 봅니다.",
            "- **용역계약**은 과업 범위, 수행 인력·자격, 성과물, 기간, 보안·저작권, 검사·검수 방식, 계속 수행 필요성을 먼저 봅니다.",
            "- **유지보수 용역**은 장애 대응시간, 정기점검 범위, 부품·라이선스 포함 여부, 보안 준수, 재위탁 가능 여부, 기존 시스템과의 연속성을 계약조건에 명확히 두는 것이 중요합니다.",
        ])
    else:
        sections.extend([
            "",
            "### 2. 먼저 볼 실무 쟁점",
            "- 계약 목적물이 물품·용역·공사 중 어디에 가까운지 먼저 정리합니다.",
            "- 그다음 계약방법, 참가자격, 낙찰자 결정방법, 가격 산정, 검사·검수, 사후관리 쟁점을 순서대로 확인합니다.",
        ])

    manual_section = render_practice_manual_cards_for_answer(cards, max_cards=4)
    if manual_section:
        sections.extend(["", manual_section])

    sections.extend([
        "",
        "### 3. 다음 단계",
        "- 금액, 기관유형, 구체 품목·과업범위가 정해지면 최신 법령 DB 기준으로 수의계약, 입찰, 지역제한, 지역업체 우대제도 적용 가능성을 별도로 검토해야 합니다.",
        "- 이 답변은 실무 매뉴얼 카드에 기반한 설명입니다. 금액 기준·조문·시행일은 최신 법령·행정규칙 기준을 우선합니다.",
    ])
    return "\n".join(sections), cards

# ─────────────────────────────────────────────
# Gemini 클라이언트 초기화 — Vertex AI (SLA 99.9%, 503 방지)
# ─────────────────────────────────────────────
# GOOGLE_APPLICATION_CREDENTIALS 환경변수로 서비스 계정 JSON 키 인증
GEMINI_HTTP_TIMEOUT_MS = int(os.getenv("GEMINI_HTTP_TIMEOUT_MS", "20000"))
_gemini_http_options = types.HttpOptions(timeout=GEMINI_HTTP_TIMEOUT_MS)
_use_vertex = os.path.exists(os.getenv("GOOGLE_APPLICATION_CREDENTIALS", ""))
if _use_vertex:
    client = genai.Client(
        vertexai=True,
        project="carbide-team-457809-a8",
        location="asia-northeast3",  # 서울 리전
        http_options=_gemini_http_options,
    )
    print("[INIT] Vertex AI 클라이언트 (서울 리전, SLA 99.9%)")
else:
    # Fallback: Vertex AI 키가 없으면 기존 AI Studio 사용
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"), http_options=_gemini_http_options)
    print("[INIT] AI Studio 클라이언트 (fallback)")
# Flash 전용 — 응답속도·비용·품질 종합 고려 시 Flash로 충분 (Pro 제거)
MODEL_ID = "gemini-2.5-flash"
FALLBACK_MODEL = "gemini-2.5-flash"

GEMINI_THINKING_BUDGET_ENABLED = os.getenv("GEMINI_THINKING_BUDGET_ENABLED", "true").lower() == "true"
GEMINI_GROUNDED_THINKING_BUDGET = int(os.getenv("GEMINI_GROUNDED_THINKING_BUDGET", "0"))
GEMINI_COMPLEX_THINKING_BUDGET = int(os.getenv("GEMINI_COMPLEX_THINKING_BUDGET", "0"))
GEMINI_EXCEPTION_THINKING_BUDGET = int(os.getenv("GEMINI_EXCEPTION_THINKING_BUDGET", "128"))
GEMINI_REWRITE_THINKING_BUDGET = int(os.getenv("GEMINI_REWRITE_THINKING_BUDGET", "0"))


def _thinking_config_for(budget: int):
    if not GEMINI_THINKING_BUDGET_ENABLED:
        return None
    try:
        return types.ThinkingConfig(thinking_budget=budget)
    except Exception as e:
        print(f"[INIT] ThinkingConfig disabled: {e}", flush=True)
        return None


def _answer_thinking_budget_for(
    user_message: str,
    *,
    base_budget: int | None = None,
    exception_budget: int | None = None,
) -> tuple[int, str]:
    """Choose answer-writing thinking budget.

    Most DB-grounded answers are faster and sufficiently stable with thinking
    disabled. Narrow exception cases keep a small budget because the answer must
    reconcile legal-system conflicts or mixed contract-object reasoning.
    """
    base = GEMINI_GROUNDED_THINKING_BUDGET if base_budget is None else int(base_budget)
    exception = GEMINI_EXCEPTION_THINKING_BUDGET if exception_budget is None else int(exception_budget)
    text = (user_message or "").replace(" ", "").lower()
    reasons: list[str] = []

    if "국가기관" in text and any(term in text for term in ("지방계약", "지역제한", "부산지역", "지역업체")):
        reasons.append("agency_law_conflict")
    if any(term in text for term in (
        "물품이야공사",
        "공사야물품",
        "물품인지공사",
        "용역인지물품",
        "물품인지용역",
        "납품설치",
        "설치포함",
        "디자인인쇄",
        "편집인쇄",
        "혼합계약",
        "주된계약목적",
    )):
        reasons.append("mixed_contract_object")
    if any(term in text for term in (
        "분리발주",
        "쪼개기",
        "나눠발주",
        "부대공사",
        "간접비",
        "공사기간",
        "계약변경",
    )):
        reasons.append("complex_contract_issue")

    if reasons:
        return max(base, exception), ",".join(dict.fromkeys(reasons))
    return base, "default_fast"


def _generate_content_bounded(*, model: str, contents, config, timeout_sec: float, label: str):
    """Run a Gemini call with a local wall-clock timeout."""
    import concurrent.futures

    request_config = config
    try:
        request_config = config.model_copy(
            update={"http_options": types.HttpOptions(timeout=max(10000, int(max(1.0, timeout_sec) * 1000)))}
        )
    except Exception:
        try:
            request_config.http_options = types.HttpOptions(timeout=max(10000, int(max(1.0, timeout_sec) * 1000)))
        except Exception:
            request_config = config

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(
        lambda: client.models.generate_content(
            model=model,
            contents=contents,
            config=request_config,
        )
    )
    try:
        return future.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError as e:
        future.cancel()
        print(f"  [MODEL_TIMEOUT] {label} exceeded {timeout_sec:.1f}s", flush=True)
        raise TimeoutError(f"{label} model call exceeded {timeout_sec:.1f}s") from e
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


_NATURAL_WRITER_INTERNAL_MARKERS = (
    "source map",
    "source_map",
    "resolved_value",
    "dataStore",
    "datastore",
    "get_company_detail",
    "function_call",
    "candidate 없음",
    "후보표 생략 대상",
    "법령 DB와 source map",
)


def _writer_has_internal_marker(text: str) -> bool:
    return any(marker in (text or "") for marker in _NATURAL_WRITER_INTERNAL_MARKERS)


def _sanitize_natural_writer_internal_terms(text: str) -> str:
    cleaned = text or ""
    replacements = {
        "내부 source map의": "내부 기준의",
        "source map의": "기준의",
        "source map": "근거 자료",
        "source_map": "근거 자료",
        "resolved_value": "확인값",
        "dataStore": "자료 저장소",
        "datastore": "자료 저장소",
        "get_company_detail": "업체 상세조회",
        "function_call": "도구 호출",
        "후보표 생략 대상": "후보 별도 확인 대상",
        "별도 후보표 생략": "후보 별도 확인",
        "후보표 방침": "후보 확인",
        "candidate 없음": "후보 없음",
        "업체 API": "업체 자료",
    }
    for src, dst in replacements.items():
        cleaned = cleaned.replace(src, dst)
    return cleaned


def _split_answer_for_natural_writer(answer: str, generation_meta: dict | None) -> tuple[str, str, str]:
    """Return writer target, suffix to preserve, and split mode.

    Candidate tables are generated by deterministic server code. We keep those
    untouched and only ask Gemini to polish the prose before the first table.
    """
    lines = (answer or "").splitlines()
    first_table_idx = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2:
            first_table_idx = idx
            break

    if first_table_idx is not None:
        prefix = "\n".join(lines[:first_table_idx]).strip()
        suffix = "\n".join(lines[first_table_idx:]).strip()
        if prefix:
            return prefix, suffix, "prose_before_table"
        return "", answer, "table_only_preserved"

    if len(answer or "") > NATURAL_LANGUAGE_WRITER_MAX_INPUT_CHARS:
        return "", answer, "too_long_without_table"
    return answer or "", "", "full_answer"


def _should_apply_natural_writer(
    *,
    answer: str,
    writer_target: str,
    split_mode: str,
    generation_meta: dict | None,
) -> tuple[bool, str]:
    if not NATURAL_LANGUAGE_WRITER_ENABLED:
        return False, "disabled"
    if NATURAL_LANGUAGE_WRITER_MODE.lower() in ("off", "false", "disabled"):
        return False, "mode_off"
    if not writer_target.strip():
        return False, split_mode or "empty_target"
    if len(writer_target) < NATURAL_LANGUAGE_WRITER_MIN_INPUT_CHARS:
        return False, "too_short"
    if len(writer_target) > NATURAL_LANGUAGE_WRITER_MAX_INPUT_CHARS:
        return False, "target_too_long"

    meta = generation_meta or {}
    if int(meta.get("model_elapsed_ms") or 0) > NATURAL_LANGUAGE_WRITER_MAX_PRIOR_MODEL_MS:
        return False, "prior_model_too_slow"

    has_internal_marker = _writer_has_internal_marker(answer)
    model_used = str(meta.get("model_used") or "")
    final_source = str(meta.get("final_answer_source") or "")
    candidate_source = str(meta.get("candidate_table_source") or "")
    formatter_chars = int(meta.get("formatter_output_chars") or 0)
    has_table_suffix = split_mode == "prose_before_table"
    model_error_statuses = meta.get("llm_payload_model_error_statuses") or []

    if NATURAL_LANGUAGE_WRITER_MODE.lower() in ("force", "always"):
        return True, "mode_force"
    if has_internal_marker:
        return True, "internal_marker_cleanup"
    if model_error_statuses:
        return False, "model_error_fallback_skip_writer"
    if model_used in ("practice_manual_fast_gate", "intent_rag_pps_qa_fast_gate"):
        return True, f"{model_used}_polish"
    if final_source in ("practice_manual_fast_answer", "intent_rag_pps_qa_fast_answer"):
        return True, f"{final_source}_polish"
    if has_table_suffix and len(writer_target) <= NATURAL_LANGUAGE_WRITER_MAX_INPUT_CHARS:
        return True, "prose_before_table_polish"
    if candidate_source in ("none", "", "not_available") and formatter_chars == 0 and len(answer) <= 1600:
        return True, "short_answer_polish"
    return False, "not_selected"


def _apply_natural_language_writer(
    answer: str,
    user_message: str,
    generation_meta: dict | None,
) -> str:
    """Polish final answer prose with Gemini, preserving deterministic tables."""
    started = time.time()
    target, suffix, split_mode = _split_answer_for_natural_writer(answer, generation_meta)
    allowed, reason = _should_apply_natural_writer(
        answer=answer,
        writer_target=target,
        split_mode=split_mode,
        generation_meta=generation_meta,
    )

    if generation_meta is not None:
        generation_meta["natural_language_writer_enabled"] = NATURAL_LANGUAGE_WRITER_ENABLED
        generation_meta["natural_language_writer_mode"] = NATURAL_LANGUAGE_WRITER_MODE
        generation_meta["natural_language_writer_model"] = NATURAL_LANGUAGE_WRITER_MODEL
        generation_meta["natural_language_writer_split_mode"] = split_mode
        generation_meta["natural_language_writer_target_chars"] = len(target or "")
        generation_meta["natural_language_writer_suffix_chars"] = len(suffix or "")
        generation_meta["natural_language_writer_applied"] = False
        generation_meta["natural_language_writer_skip_reason"] = reason

    if not allowed:
        return _sanitize_natural_writer_internal_terms(answer)

    prompt = f"""
아래 [원래 답변]을 공공계약 담당자가 읽기 쉬운 자연스러운 한국어로만 다듬어 주세요.

[엄격한 조건]
- 법적 결론, 금액, 조문명, 업체명은 바꾸지 마세요.
- 새로운 법령·판단·업체·수치를 추가하지 마세요.
- 표, 후보업체 목록, 행/열 정보는 이 요청에 포함되지 않았더라도 뒤에 원문 그대로 붙습니다. 표를 새로 만들지 마세요.
- 내부 시스템명, 함수명, source map, resolved_value, dataStore 같은 개발/검색 용어는 사용자에게 보이지 않게 일반 표현으로 바꾸세요.
- 근거가 부족하다는 취지의 문장은 유지하세요.
- 인사말이나 작업 설명 없이 최종 답변 본문만 출력하세요.

[사용자 질문]
{user_message}

[원래 답변]
{target[:NATURAL_LANGUAGE_WRITER_MAX_INPUT_CHARS]}
""".strip()

    try:
        response = _generate_content_bounded(
            model=NATURAL_LANGUAGE_WRITER_MODEL,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.1,
                thinking_config=_thinking_config_for(GEMINI_REWRITE_THINKING_BUDGET),
            ),
            timeout_sec=NATURAL_LANGUAGE_WRITER_TIMEOUT_SEC,
            label="natural_language_writer",
        )
        rewritten = (response.text or "").strip()
        if not rewritten:
            raise ValueError("empty writer response")
        if _writer_has_internal_marker(rewritten):
            raise ValueError("writer output still contains internal marker")
        if "|" in rewritten and split_mode == "prose_before_table":
            raise ValueError("writer attempted to create a table")

        final_answer = rewritten
        if suffix:
            final_answer = f"{rewritten}\n\n{suffix}".strip()
        final_answer = _sanitize_natural_writer_internal_terms(final_answer)

        if generation_meta is not None:
            usage = getattr(response, "usage_metadata", None)
            generation_meta["natural_language_writer_applied"] = True
            generation_meta["natural_language_writer_skip_reason"] = ""
            generation_meta["natural_language_writer_reason"] = reason
            generation_meta["natural_language_writer_elapsed_ms"] = int((time.time() - started) * 1000)
            generation_meta["natural_language_writer_prompt_chars"] = len(prompt)
            generation_meta["natural_language_writer_output_chars"] = len(rewritten)
            generation_meta["natural_language_writer_table_preserved"] = bool(suffix)
            generation_meta["natural_language_writer_usage"] = _to_jsonable_for_meta(usage)
        return final_answer
    except Exception as exc:
        if generation_meta is not None:
            generation_meta["natural_language_writer_applied"] = False
            generation_meta["natural_language_writer_skip_reason"] = f"fallback:{type(exc).__name__}"
            generation_meta["natural_language_writer_error"] = str(exc)[:200]
            generation_meta["natural_language_writer_elapsed_ms"] = int((time.time() - started) * 1000)
        print(f"  [NATURAL_WRITER] fallback to original answer: {exc}", flush=True)
        return _sanitize_natural_writer_internal_terms(answer)


def _is_markdown_table_line(line: str) -> bool:
    stripped = (line or "").strip()
    return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2


def _looks_like_candidate_or_company_table(table_text: str) -> bool:
    """Return True only for company/candidate tables that server formatter owns."""
    compact = re.sub(r"\s+", "", table_text or "").lower()
    if not compact:
        return False

    identity_terms = (
        "업체명", "기업명", "회사명", "사업자", "소재지", "주소",
        "대표품목", "등록상품명", "제품명",
    )
    candidate_context_terms = (
        "후보유형", "조달등록", "쇼핑몰/mas", "mas", "정책기업",
        "직접생산", "중기경쟁", "기술개발", "혁신", "인증번호",
        "확인포인트", "검토가능경로", "부산업체후보", "지역업체후보",
    )

    has_identity = any(term in compact for term in identity_terms)
    has_candidate_context = any(term in compact for term in candidate_context_terms)
    return has_identity and has_candidate_context


def _strip_candidate_or_company_markdown_tables(text: str) -> tuple[str, int]:
    """Remove only LLM-created company/candidate Markdown tables.

    Legal comparison tables and route/risk comparison tables remain intact.
    """
    lines = (text or "").splitlines()
    output: list[str] = []
    removed_count = 0
    idx = 0

    while idx < len(lines):
        if _is_markdown_table_line(lines[idx]):
            start = idx
            while idx < len(lines) and _is_markdown_table_line(lines[idx]):
                idx += 1
            block = lines[start:idx]
            block_text = "\n".join(block)
            if len(block) >= 2 and _looks_like_candidate_or_company_table(block_text):
                removed_count += 1
                continue
            output.extend(block)
            continue

        output.append(lines[idx])
        idx += 1

    cleaned = "\n".join(output)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip(), removed_count


def _to_jsonable_for_meta(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_json_dict"):
        try:
            return value.to_json_dict()
        except Exception:
            pass
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except Exception:
            pass
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_to_jsonable_for_meta(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _to_jsonable_for_meta(v) for k, v in value.items()}
    return str(value)

# ─────────────────────────────────────────────
# Function Calling 도구 정의
# ─────────────────────────────────────────────

law_tools = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="search_law",
                description="법령명으로 검색. 약칭 자동변환 지원(지방계약법→지방자치단체를 당사자로 하는 계약에 관한 법률). MST 식별자 획득용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색할 법령명 (예: '지방계약법', '근로기준법', '조달사업법')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_law_text",
                description="법령 MST 식별자로 특정 조문의 원문을 조회합니다. search_law 결과에서 얻은 MST를 사용하세요.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "mst": types.Schema(
                            type="STRING",
                            description="법령 MST 식별자 (search_law 결과에서 획득)"
                        ),
                        "jo": types.Schema(
                            type="STRING",
                            description="조문번호 (예: '제25조', '제13조의 2'). 생략하면 전체 조문 조회"
                        ),
                    },
                    required=["mst"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_interpretations",
                description="해석례(유권해석) 검색. 법령 해석에 관한 행정부 질의회신을 찾을 때 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색 키워드 (예: '수의계약', '지역제한 입찰')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_decisions",
                description="판례 검색. 대법원 판결, 감사원 결정 등을 찾을 때 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색 키워드 (예: '지역제한 입찰 위법')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_annexes",
                description="별표/서식 조회. 금액 기준표, 요율표, 처분기준표 등이 별표에 있을 때 사용. HWP/HWPX 자동 Markdown 변환.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "law_name": types.Schema(
                            type="STRING",
                            description="법령명 (예: '산업안전보건법', '지방계약법 시행령')"
                        ),
                    },
                    required=["law_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_full_research",
                description="종합 리서치. 법령명이 불명확한 복합 질문에 사용. AI검색→법령→판례→해석례 병렬 수행.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="자연어 질문 (예: '수의계약 한도', '지역업체 우선구매')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_action_basis",
                description="처분/허가/인가의 법적 근거 종합 추적. 법체계→해석례→판례→행심 병렬 조회. 법령명이 특정된 질문에 적합.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="법령명 + 주제 (예: '지방계약법', '건축법 허가')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_law_system",
                description="법령 체계 분석. 법률→시행령→시행규칙 3단 구조 + 위임 조문 + 하위법령을 한번에 조회.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="법령명 (예: '지방계약법', '건축법')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_company_detail",
                description="[2단계 필수] 업체 상세 정보 조회 (Master Detail API). 1단계 검색을 통해 얻은 company_id로 업체의 면허, 품목, 쇼핑몰상품, 인증, 정책기업 정보 등을 구체적으로 확인합니다. 수의계약이나 적격성 판단 전 반드시 호출해야 합니다.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "company_id": types.Schema(
                            type="STRING",
                            description="1단계 검색 결과에서 획득한 company_id"
                        ),
                    },
                    required=["company_id"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_company_by_product",
                description="[1단계] 부산 업체를 대표품목으로 검색. 'LED조명'→'LED'. 검색 결과의 company_id를 사용해 get_company_detail을 호출하세요.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색할 품목명 (예: 'LED', 'CCTV')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_company_by_license",
                description="[1단계] 부산 업체를 면허/업종으로 검색. 공사/용역 업체 찾을 때 사용. 결과의 company_id로 get_company_detail 호출.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="면허/업종명 (예: '전기공사', '소방시설업')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_company_by_policy",
                description="[1단계] 부산 업체를 정책기업(여성, 장애인 등)으로 검색. 결과의 company_id로 get_company_detail 호출.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="정책 분류 (예: '여성기업', '장애인기업', '사회적기업')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_shopping_mall_product",
                description="[1단계] 나라장터 종합쇼핑몰에 등록된 부산 업체의 MAS(다수공급자계약) 상품 검색. 결과의 company_id로 get_company_detail 호출.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "product_name": types.Schema(
                            type="STRING",
                            description="품목명 (예: 'LED', '소방', '사무용가구')"
                        ),
                    },
                    required=["product_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_shopping_mall_supplier",
                description="[1단계] 쇼핑몰에 등록된 부산 공급사를 업체명으로 검색. 결과의 company_id로 get_company_detail 호출.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "company_keyword": types.Schema(
                            type="STRING",
                            description="업체명 검색어"
                        ),
                    },
                    required=["company_keyword"],
                ),
            ),
            # ── 행정규칙 (훈령/예규/고시) ──
            types.FunctionDeclaration(
                name="search_admin_rule",
                description="행정규칙(훈령/예규/고시) 검색. 계약집행기준, 낙찰자결정기준, 업무처리규정 등 행정규칙 원문을 찾을 때 사용. search_law로 못 찾는 행정규칙은 이 도구로 검색.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="검색 키워드 (예: '입찰 계약집행기준', '낙찰자 결정기준', '내자구매업무 처리규정')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="get_admin_rule",
                description="행정규칙 전문 조회. search_admin_rule 결과에서 얻은 행정규칙일련번호(ID)를 사용하여 원문 전체를 조회합니다.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "rule_id": types.Schema(
                            type="STRING",
                            description="행정규칙일련번호 (예: '2100000261486')"
                        ),
                    },
                    required=["rule_id"],
                ),
            ),
            # ── 추가 체인 도구 ──
            types.FunctionDeclaration(
                name="chain_procedure_detail",
                description="계약 절차·필요서류·비용을 한번에 안내. '수의계약 절차가 어떻게 돼?', '입찰 참가 서류가 뭐야?' 같은 절차 질문에 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="절차 관련 질문 (예: '수의계약 절차', '입찰 참가자격')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_ordinance_compare",
                description="조례와 상위법 비교 분석. 부산시 조례의 지역업체 우대 조항, 조달 관련 조례 등을 상위법과 비교할 때 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="조례 관련 질문 (예: '부산시 지역상품 우선구매 조례', '지역업체 우대')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_amendment_track",
                description="법령 개정 추적. 신구대조표와 개정 연혁을 조회. '이 법 최근에 뭐 바뀌었어?', '개정 사항 알려줘' 같은 질문에 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="법령명 (예: '지방계약법', '조달사업법')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            types.FunctionDeclaration(
                name="chain_document_review",
                description="계약서·약관의 법적 리스크 분석. 계약 조항의 적법성을 검토할 때 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "query": types.Schema(
                            type="STRING",
                            description="계약서 관련 질문 (예: '다수공급자계약 특수조건 검토', '계약 해지 조건')"
                        ),
                    },
                    required=["query"],
                ),
            ),
            # ── 판례/해석례 전문 조회 ──
            types.FunctionDeclaration(
                name="get_decision_text",
                description="판례·해석례 전문 조회. search_decisions 결과에서 얻은 ID로 판결문 본문을 확인할 때 사용.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "decision_id": types.Schema(
                            type="STRING",
                            description="판례/해석례 ID (search_decisions 결과에서 획득)"
                        ),
                        "domain": types.Schema(
                            type="STRING",
                            description="도메인: precedent(판례), interpretation(해석례), admin_appeal(행정심판). 기본값: precedent"
                        ),
                    },
                    required=["decision_id"],
                ),
            ),
            # ── 인증·기술개발제품 검색 ──
            types.FunctionDeclaration(
                name="search_certified_product",
                description="[1단계] 인증제품(일반인증 등) 보유 부산 업체 검색. 결과의 company_id로 get_company_detail 호출.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "product_name": types.Schema(
                            type="STRING",
                            description="품목명 (예: 'LED')"
                        ),
                    },
                    required=["product_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_innovation_product",
                description="[1단계] 혁신제품/혁신시제품 지정 부산 업체 검색. 결과의 company_id로 get_company_detail 호출.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "product_name": types.Schema(
                            type="STRING",
                            description="품목명"
                        ),
                    },
                    required=["product_name"],
                ),
            ),
            types.FunctionDeclaration(
                name="search_excellent_procurement_product",
                description="[1단계] 우수조달물품 인증 보유 부산 업체 검색. 결과의 company_id로 get_company_detail 호출.",
                parameters=types.Schema(
                    type="OBJECT",
                    properties={
                        "product_name": types.Schema(
                            type="STRING",
                            description="품목명"
                        ),
                    },
                    required=["product_name"],
                ),
            ),
        ]
    )
]


def _execute_function_call(function_call) -> str:
    """Function call을 실행하고 결과를 반환. MCP 원격 엔드포인트 사용."""
    from policies.timeout_policy import get_timeout
    
    TOOL_ALIAS_MAP = {
        "search_local_company_by_product": "search_company_by_product",
        "search_local_company_by_license": "search_company_by_license",
        "search_local_company_by_category": "search_company_by_category",
        "search_shopping_mall": "search_shopping_mall_product",
        "search_innovation_products": "search_innovation_product",
        "search_tech_development_products": "search_certified_product"
    }
    
    raw_name = function_call.name
    name = TOOL_ALIAS_MAP.get(raw_name, raw_name)
    args = dict(function_call.args) if function_call.args else {}
    global _cited_laws

    # P0-5: timeout_policy 환경변수 기반 timeout 사용 (하드코딩 제거)
    timeout = get_timeout(name)

    def _run_with_timeout(func, *a, **kw):
        """MCP 함수를 타임아웃 내에 실행. 초과 시 Fallback 메시지 반환."""
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
        pool = ThreadPoolExecutor(max_workers=1)
        future = pool.submit(func, *a, **kw)
        try:
            res = future.result(timeout=timeout)
            pool.shutdown(wait=False)
            return res
        except FuturesTimeout:
            print(f"  [MCP TIMEOUT] {name} 호출 {timeout}초 초과")
            pool.shutdown(wait=False)
            return json.dumps({
                "warning": f"외부 API 응답 지연으로 '{name}' 결과를 가져오지 못했습니다. "
            }, ensure_ascii=False)
        except Exception as e:
            pool.shutdown(wait=False)
            return json.dumps({"warning": f"API 오류: {str(e)}"}, ensure_ascii=False)

    try:
        if name == "search_law":
            return _run_with_timeout(mcp.search_law, args.get("query", ""))
        elif name == "get_law_text":
            result = _run_with_timeout(mcp.get_law_text, mst=args.get("mst"), jo=args.get("jo"))
            # 인용 조문 저장
            if isinstance(result, str) and "warning" not in result:
                _cited_laws.append({"type": "조문", "args": args, "text": result[:2000]})
            return result
        elif name == "search_interpretations":
            return _run_with_timeout(mcp.search_interpretations, args.get("query", ""))
        elif name == "search_decisions":
            return _run_with_timeout(mcp.search_decisions, args.get("query", ""))
        elif name == "get_annexes":
            return _run_with_timeout(mcp.get_annexes, args.get("law_name", ""), args.get("annex_no"))
        elif name == "chain_full_research":
            return _run_with_timeout(mcp.chain_full_research, args.get("query", ""))
        elif name == "chain_action_basis":
            return _run_with_timeout(mcp.chain_action_basis, args.get("query", ""))
        elif name == "chain_law_system":
            return _run_with_timeout(mcp.chain_law_system, args.get("query", ""))
        # ── 행정규칙 (훈령/예규/고시) ──
        elif name == "search_admin_rule":
            return _run_with_timeout(mcp.search_admin_rule, args.get("query", ""))
        elif name == "get_admin_rule":
            return _run_with_timeout(mcp.get_admin_rule, args.get("rule_id", ""))
        # ── 추가 체인 도구 ──
        elif name == "chain_procedure_detail":
            return _run_with_timeout(mcp.chain_procedure_detail, args.get("query", ""))
        elif name == "chain_ordinance_compare":
            return _run_with_timeout(mcp.chain_ordinance_compare, args.get("query", ""))
        elif name == "chain_amendment_track":
            return _run_with_timeout(mcp.chain_amendment_track, args.get("query", ""))
        elif name == "chain_document_review":
            return _run_with_timeout(mcp.chain_document_review, args.get("query", ""))
        # ── 판례/해석례 전문 조회 ──
        elif name == "get_decision_text":
            return _run_with_timeout(
                mcp.get_decision_text,
                args.get("decision_id", ""),
                args.get("domain", "precedent"),
            )
        # ── 부산 지역업체 검색 (Monitoring API 통합) ──
        elif name == "get_company_detail":
            data = company_api.get_company_detail(args.get("company_id", ""))
            return format_company_detail_for_llm(data)
        elif name == "search_company_by_product":
            data = company_api.search_by_product(args.get("query", ""))
            return format_company_for_llm(data, max_results=10)
        elif name == "search_company_by_license":
            data = company_api.search_by_license(args.get("query", ""))
            return format_company_for_llm(data, max_results=10)
        elif name == "search_company_by_policy":
            data = company_api.search_by_policy(args.get("query", ""))
            return format_company_for_llm(data, max_results=10)
        elif name == "search_shopping_mall_product":
            data = company_api.search_shopping_mall_product(args.get("product_name", ""))
            return format_company_for_llm(data, max_results=10)
        elif name == "search_shopping_mall_supplier":
            data = company_api.search_shopping_mall_supplier(args.get("company_keyword", ""))
            return format_company_for_llm(data, max_results=10)
        elif name == "search_certified_product":
            data = company_api.search_certified_product(args.get("product_name", ""))
            return format_company_for_llm(data, max_results=10)
        elif name == "search_innovation_product":
            data = company_api.search_innovation_product(args.get("product_name", ""))
            return format_company_for_llm(data, max_results=10)
        elif name == "search_excellent_procurement_product":
            data = company_api.search_excellent_procurement_product(args.get("product_name", ""))
            return format_company_for_llm(data, max_results=10)
        else:
            return json.dumps({"error": f"알 수 없는 함수: {name}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


import re

def _verify_and_annotate(answer: str) -> str:
    """
    AI 답변의 법령 인용을 verify_citations로 교차검증.
    검증 오류 발견 시 답변 하단에 간결한 경고 추가.
    """
    # 법령 인용 패턴이 없으면 스킵 (성능 최적화)
    if not re.search(r'제\d+조', answer):
        return answer

    try:
        print("  [검증] verify_citations 실행 중...")
        verification = mcp.verify_citations(answer)

        if not verification or "error" in verification.lower():
            return answer  # 검증 실패 시 원본 유지

        # 환각(HALLUCINATION) 감지 여부 확인
        hallucination_detected = "HALLUCINATION_DETECTED" in verification

        # 일반적인 검증 문제 여부 확인
        has_issues = hallucination_detected or any(kw in verification for kw in [
            "NOT_FOUND", "불일치", "확인불가", "없는",
            "mismatch", "invalid", "not found"
        ])

        if has_issues:
            # 검증 결과를 간결하게 요약 (원시 데이터를 그대로 출력하지 않음)
            answer += "\n\n---\n"
            if hallucination_detected:
                answer += "⚠️ **인용 검증 주의**: 일부 법령 인용의 정확성을 확인하지 못했습니다. 법제 담당 부서와 교차 확인을 권장합니다.\n"
            else:
                answer += "🔍 **인용 검증**: 일부 조항의 법령명 매칭이 불명확합니다. 법제처 사이트에서 직접 확인을 권장합니다.\n"
            print(f"  [검증] 인용 문제 발견 - 간결 경고 추가")
        else:
            answer += "\n\n✅ *법령 인용이 검증되었습니다.*"
            print("  [검증] ✅ 인용 정확성 확인 완료")

        return answer

    except Exception as e:
        print(f"  [검증] 검증 중 오류 (무시): {e}")
        return answer  # 검증 실패해도 원본 답변 유지


def _search_pps_qa(query: str, n_results: int = 3) -> str:
    """조달청 질의응답 DB에서 유사 해석사례 검색 (RAG)."""
    try:
        from ingest_pps_qa import search_qa
        results = search_qa(query, n_results=n_results)

        if not results:
            return ""

        lines = []
        for i, r in enumerate(results):
            lines.append(f"= 해석사례 {i+1}: {r['title']} ({r['date']})")
            lines.append(f"  분류: {r['category']}")
            if r.get('answer'):
                answer_summary = r['answer'][:800]
                lines.append(f"  회신: {answer_summary}")
            lines.append("")

        context = "\n".join(lines)
        return context[:3000]

    except Exception as e:
        print(f"  [RAG-QA] 검색 실패: {e}")
        return ""


def _search_manuals(query: str, n_results: int = 3, query_vector: list = None) -> str:
    """계약 매뉴얼 RAG에서 관련 내용 검색. 멀티컬렉션 지원 (manuals_1, manuals_2, ...)."""
    try:
        import chromadb
        import os
        from embedding import get_query_embedding_fn
        chroma_dir = os.getenv("CHROMA_MANUALS_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma"))
        client = chromadb.PersistentClient(path=chroma_dir)
        ef = get_query_embedding_fn()

        COLLECTION_PREFIX = "manuals_"
        all_docs = []

        for col_info in client.list_collections():
            if not col_info.name.startswith(COLLECTION_PREFIX):
                continue
            try:
                collection = client.get_collection(name=col_info.name, embedding_function=ef)
                if query_vector:
                    results = collection.query(query_embeddings=[query_vector], n_results=n_results)
                else:
                    results = collection.query(query_texts=[query], n_results=n_results)

                if results["documents"] and results["documents"][0]:
                    for doc, meta, dist in zip(
                        results["documents"][0],
                        results["metadatas"][0],
                        results["distances"][0],
                    ):
                        all_docs.append({"doc": doc, "meta": meta, "distance": dist})
            except Exception:
                continue

        if not all_docs:
            return ""

        # 거리순 정렬 후 상위 n_results
        all_docs.sort(key=lambda x: x["distance"])
        top_docs = all_docs[:n_results]

        lines = []
        for i, item in enumerate(top_docs):
            source = item["meta"].get("source", "매뉴얼")
            page = item["meta"].get("page", "?")
            lines.append(f"= 매뉴얼 {i+1}: [{source}] p.{page}")
            lines.append(item["doc"][:600])
            lines.append("")

        context = "\n".join(lines)
        return context[:3000]

    except Exception as e:
        print(f"  [RAG-MANUAL] 검색 실패: {e}")
        return ""


def _search_law_rag(query: str, n_results: int = 5, agency_type: str = None) -> str:
    """핵심 법령 RAG에서 관련 조문 검색."""
    try:
        from ingest_laws import search_laws
        results = search_laws(query, n_results=n_results, agency_type=agency_type)

        if not results:
            return ""

        lines = []
        for i, r in enumerate(results):
            lines.append(f"= 법령 {i+1}: [{r['law']}] {r['article']} {r['title']}")
            lines.append(r['text'][:600])
            lines.append("")

        context = "\n".join(lines)
        return context[:4000]

    except Exception as e:
        print(f"  [RAG-LAW] search failed: {e}")
        return ""


# ─────────────────────────────────────────────
# 병렬 RAG 검색 (임베딩 1회 + ThreadPool)
# ─────────────────────────────────────────────
def _parallel_rag_search(query: str, agency_type: str = None) -> dict:
    """RAG 검색: QA + 매뉴얼만 사용. 혁신/기술개발은 업체 API에서 담당.
    임베딩 로드 3초 제한. ChromaDB 미연결 시 빈 결과 즉시 반환."""
    from concurrent.futures import ThreadPoolExecutor
    import time

    start = time.time()
    results = {"qa": "", "manual": ""}

    # 1. 임베딩 (실패 또는 3초 초과 시 스킵)
    try:
        from embedding import encode_query
        query_vector = encode_query(query)
    except Exception as e:
        print(f"  [RAG] 임베딩 실패, 스킵: {e}")
        return results
    
    embed_time = time.time() - start
    print(f"  [RAG] 임베딩 완료: {embed_time:.1f}초")
    
    if embed_time > 3.0:
        print(f"  [RAG] 임베딩 {embed_time:.1f}초 > 3초, 검색 스킵 (콜드스타트)")
        return results

    # 2. QA + 매뉴얼만 검색 (타임아웃 3초)
    def search_qa():
        return _search_pps_qa(query)

    def search_manual():
        return _search_manuals(query, query_vector=query_vector)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            "qa": pool.submit(search_qa),
            "manual": pool.submit(search_manual),
        }
        for key, future in futures.items():
            try:
                results[key] = future.result(timeout=3)
            except Exception as e:
                print(f"  [RAG] {key} 검색 실패/타임아웃: {e}")
                results[key] = ""

    total_time = time.time() - start
    print(f"  [RAG] 검색 완료: {total_time:.1f}초 (QA+매뉴얼만)")
    return results


# ─────────────────────────────────────────────
# 기관별 법체계 가이드 MAP (동적 주입)
# ─────────────────────────────────────────────
_COMMON_PROCUREMENT = (
    "\n[공통 조달 원칙 — 모든 기관 공통 적용]\n"
    "  · 우수조달물품(시행령 제25조 제1항 제6호 라목): 수의계약 검토 후보 — 적용 조건 및 지정 상태 확인 필요\n"
    "  · 혁신제품(시행령 제25조 제1항 제8호): 수의계약 검토 후보 — 지정 상태 및 혁신장터 등록 여부 확인 필요\n"
    "  · 직접생산확인증명서: 중소기업 제품 수의계약 시 필수\n"
    "  · ⛔ 특정 제품(혁신제품, 우선구매 대상 등)에 대해 '금액 제한 없이 수의계약이 가능하다' 또는 '수의계약이 가능합니다'라고 절대 단정짓지 마세요. 반드시 '해당 요건(지정 상태, 등록 여부 등)을 확인한 후 수의계약 검토가 가능하다'고 유보적으로 답변하세요.\n"
)

_AGENCY_GUIDE_MAP = {
    # 1. 지방자치단체 그룹 (부산시, 자치구·군, 교육청)
    "local_government": (
        "\n\n[적용 법체계: 지방자치단체 (부산시, 구·군, 교육청)]\n"
        "1. 법적 위계: 지방계약법 → 시행령 → 시행규칙 → 행정규칙(예규·고시) → 자치법규(조례)\n"
        "2. 실무 검증 (MCP 필수 실행):\n"
        "   · search_law(\"지방자치단체 입찰 및 계약 집행기준\") : 수의계약 한도 및 절차 확인\n"
        "   · search_law(\"지방자치단체 입찰 시 낙찰자 결정기준\") : 적격심사 및 지역업체 가점 확인\n"
        "3. 지역 특화 (RAG & MCP 교차):\n"
        "   · search_law(\"부산광역시 지역상품 우선구매\") : 부산시 조례에 따른 지역업체 우대 확인\n"
        "4. 교육청 특이사항: 교육부 소관 '지방교육행정기관 재무회계 규칙' 등 추가 확인 필요 시 검색.\n"
        "⛔ 국가계약법 기준으로 답변하면 오답입니다! 절대 혼동 금지!\n"
        + _COMMON_PROCUREMENT
    ),

    # 2. 부산시 출자·출연기관 그룹 (공사·공단, 진흥원 등)
    "invested_institution": (
        "\n\n[적용 법체계: 부산광역시 출자·출연기관]\n"
        "1. 법적 위계: 지방출자출연법 → 해당 기관 자체 계약규정 → (준용) 지방계약법\n"
        "2. 실무 검증:\n"
        "   · 기본적으로 '지방계약법' 체계를 따르되, 기관 자체 규정이 우선함.\n"
        "   · search_law(\"지방자치단체 입찰 및 계약 집행기준\") : 준용되는 세부 절차 확인\n"
        "   · search_law(\"지방자치단체 출자 출연 기관\") : 출자출연법 관련 규정 확인\n"
        "3. 지역 우대: 부산시 산하기관으로서 '부산광역시 지역상품 우선구매 조례' 이행 대상임을 강조.\n"
        "⚠️ 자체 계약규정이 지방계약법과 다를 수 있으므로, 해당 기관 규정 우선 확인 필요!\n"
        + _COMMON_PROCUREMENT
    ),

    # 3. 국가기관 그룹 (중앙부처 및 소속기관)
    "national_agency": (
        "\n\n[적용 법체계: 국가기관 (중앙행정기관)]\n"
        "1. 법적 위계: 국가계약법 → 시행령 → 시행규칙 → 행정규칙(예규·고시)\n"
        "2. 실무 검증 (MCP 필수 실행):\n"
        "   · search_law(\"정부 입찰·계약 집행기준\") : 수의계약 및 계약 일반 원칙 확인\n"
        "   · search_law(\"적격심사기준\") : 국가기관 발주 건의 낙찰자 결정 기준 확인\n"
        "3. 특이사항: WTO 정부조달협정 한도 금액(고시) 및 특정조달 특례규정 확인 필수.\n"
        "⛔ 지방계약법 기준으로 답변하면 오답입니다! 절대 혼동 금지!\n"
        + _COMMON_PROCUREMENT
    ),

    # 4. 국가 공공기관 그룹 (공기업, 준정부기관)
    "public_corporation": (
        "\n\n[적용 법체계: 국가 공공기관 (공기업, 준정부기관)]\n"
        "1. 법적 위계: 공운법 → 공기업·준정부기관 계약사무규칙 → (준용) 국가계약법\n"
        "2. 실무 검증 (MCP 필수 실행):\n"
        "   · search_law(\"공기업·준정부기관 계약사무규칙\") : 기관 전용 계약 원칙 확인\n"
        "   · search_law(\"기타공공기관 계약사무 운영규정\") : 해당 시 적용 여부 확인\n"
        "3. 핵심 포인트: 경영평가와 연계된 '혁신제품 구매' 및 '중소기업 판로 지원' 규정 우선 검토.\n"
        "⚠️ 지방계약법·국가계약법과 기준이 다를 수 있으므로 주의!\n"
        + _COMMON_PROCUREMENT
    ),

    # 기본값 — 소속 미지정 시
    "default": (
        "\n\n[적용 법체계: 부산광역시 (지방자치단체) — 기본값]\n"
        "★ 사용자가 소속기관을 밝히지 않았으므로 부산광역시(지방자치단체) 기준으로 답변합니다.\n"
        "1. 법적 위계: 지방계약법 → 시행령 → 시행규칙 → 행정규칙(예규·고시) → 자치법규(조례)\n"
        "2. 실무 검증 (MCP 필수 실행):\n"
        "   · search_law(\"지방자치단체 입찰 및 계약 집행기준\") : 계약절차, 소액수의 한도 확인\n"
        "   · search_law(\"지방자치단체 입찰 시 낙찰자 결정기준\") : 적격심사 배점·가점 확인\n"
        "3. 지역 특화:\n"
        "   · search_law(\"부산광역시 지역상품 우선구매\") : 부산시 조례 확인\n"
        + _COMMON_PROCUREMENT
        + "\n→ 답변 하단에 반드시 포함: '다른 기관(국가기관·공기업 등) 기준이 궁금하시면 말씀해 주세요.'\n"
    ),
}


def _normalize_agency_type(agency_type: str) -> str:
    """사이드바 드롭다운 값 → prompt_assembler._AGENCY_GUIDE_MAP 키 변환.
    P0-7: legacy MAP 키(local_gov 등)와 assembler MAP 키(local_government 등) 통일.
    """
    if not agency_type:
        return "default"
    mapping = {
        # ── identity: 이미 정규화된 키가 들어오면 그대로 반환 ──
        "local_government": "local_government",
        "national_agency": "national_agency",
        "public_corporation": "public_corporation",
        "invested_institution": "invested_institution",
        # 지방자치단체 그룹 → local_government (assembler와 통일)
        "지방자치단체": "local_government",
        "부산광역시": "local_government",
        "부산시": "local_government",
        "자치구": "local_government",
        "구청": "local_government",
        "군청": "local_government",
        "교육청": "local_government",
        # legacy 호환
        "local_gov": "local_government",
        # 부산 출자·출연기관 그룹 → invested_institution (assembler와 통일)
        "출자출연기관": "invested_institution",
        "부산도시공사": "invested_institution",
        "부산교통공사": "invested_institution",
        "부산시설공단": "invested_institution",
        "부산관광공사": "invested_institution",
        "부산정보산업진흥원": "invested_institution",
        "부산산업과학혁신원": "invested_institution",
        "지방공기업": "invested_institution",
        # legacy 호환
        "busan_entity": "invested_institution",
        # 국가기관 그룹 → national_agency (assembler와 통일)
        "국가기관": "national_agency",
        "중앙부처": "national_agency",
        "national_gov": "national_agency",
        # 국가 공공기관 그룹 → public_corporation (assembler와 통일)
        "공기업": "public_corporation",
        "준정부기관": "public_corporation",
        "공기업/준정부기관": "public_corporation",
        "공공기관": "public_corporation",
        "public_agency": "public_corporation",
    }
    return mapping.get(agency_type, "default")

# 사용자 친화적 도구 레이블 (보안: 내부 함수명/서버 주소 노출 방지)
TOOL_LABELS = {
    "search_law": "🔍 법령 검색 중",
    "get_law_text": "📜 조문 원문 확인 중",
    "search_interpretations": "🔍 해석례 검색 중",
    "search_decisions": "🔍 판례 검색 중",
    "get_annexes": "📊 별표/서식 조회 중",
    "chain_full_research": "🔍 종합 법령 연구 중",
    "chain_action_basis": "🔍 법체계 분석 중",
    "chain_law_system": "🔍 법령 체계도 조회 중",
    "search_local_company_by_product": "🏢 지역업체 품목 검색 중",
    "search_local_company_by_license": "🏢 지역업체 면허 검색 중",
    "search_local_company_by_category": "🏢 지역업체 분류 검색 중",
    "search_innovation_products": "🏷️ 혁신제품 검색 중",
    "search_tech_development_products": "🏷️ 기술개발제품 인증 검색 중",
}


def chat(user_message: str, history: list[dict] = None, progress_callback=None, agency_type: str = None) -> tuple[str, list[dict]]:
    """
    사용자 메시지를 받아 Gemini와 대화.
    PROMPT_MODE에 따라 legacy 또는 v1.4.4 dynamic 파이프라인 분기.
    """
    if history is None:
        history = []

    if PROMPT_MODE == "dynamic_v1_4_4":
        return _chat_v144(user_message, history, progress_callback, agency_type)
    # else: legacy 모드 (기존 로직 그대로)
    
    global _cited_laws, _current_evidence_context_meta
    _cited_laws = []  # 매 답변마다 초기화
    _current_evidence_context_meta = {}

    # ── 대화 이력 윈도잉 (Rate Limit + 비용 방지) ──
    # 최근 10턴(user+model 20메시지)만 유지, 오래된 이력은 자동 삭제
    MAX_HISTORY_TURNS = 10  # 턴 수 (1턴 = user + model)
    MAX_HISTORY_MESSAGES = MAX_HISTORY_TURNS * 2
    if len(history) > MAX_HISTORY_MESSAGES:
        trimmed_count = len(history) - MAX_HISTORY_MESSAGES
        history = history[-MAX_HISTORY_MESSAGES:]
        print(f"  [WINDOW] 대화 이력 윈도잉: {trimmed_count}개 메시지 삭제, {len(history)}개 유지")

    # 대화 이력을 Gemini 형식으로 변환
    contents = []
    for msg in history:
        contents.append(
            types.Content(
                role=msg["role"],
                parts=[types.Part.from_text(text=msg["text"])]
            )
        )

    # === RAG: 5개 소스 병렬 검색 (임베딩 1회) ===
    if progress_callback:
        progress_callback("📚 관련 데이터베이스 병렬 검색 중...")
    rag = _parallel_rag_search(user_message, agency_type=agency_type)

    # 현재 사용자 메시지 추가 (RAG 컨텍스트 포함)
    user_text = user_message
    rag_parts = []
    if rag.get("law"):
        rag_parts.append(f"[참고용 보조자료: 법령 조문 — MCP 검색 결과와 다르면 MCP가 우선]\n{rag['law']}")
    if rag.get("qa"):
        rag_parts.append(f"[참고용 보조자료: 조달청 질의응답 — MCP 검색 결과와 다르면 MCP가 우선]\n{rag['qa']}")
    if rag.get("manual"):
        rag_parts.append(f"[참고용 보조자료: 계약 매뉴얼 — MCP 검색 결과와 다르면 MCP가 우선]\n{rag['manual']}")
    if rag.get("innovation"):
        rag_parts.append(f"[부산 지역 혁신제품 — 수의계약 검토 후보, 지정 상태·혁신장터 등록 여부 확인 필요]\n{rag['innovation']}")
    if rag.get("tech"):
        rag_parts.append(f"[부산 지역 기술개발제품 인증 — 우선구매/수의계약 검토 후보, 인증 상태 확인 필요]\n{rag['tech']}")
    
    if rag_parts:
        user_text = "\n\n".join(rag_parts) + f"\n\n[사용자 질문]\n{user_message}"

    contents.append(
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_text)]
        )
    )

    # Gemini 설정 — 현재 날짜를 시스템 프롬프트에 동적 주입
    from datetime import datetime
    today = datetime.now().strftime("%Y년 %m월 %d일")

    # 기관 유형별 적용 법체계 동적 주입 (AGENCY_GUIDE_MAP)
    agency_guide = _AGENCY_GUIDE_MAP.get(
        _normalize_agency_type(agency_type),
        _AGENCY_GUIDE_MAP["default"]
    )

    date_instruction = (
        f"\n\n[조회 시점: {today}]\n"
        f"법령 조회 결과를 인용할 때 반드시 \"{today} 기준\"임을 답변에 명시하세요.\n"
        f"예: \"지방계약법 시행령 제25조({today} 기준)에 따르면...\""
        f"{agency_guide}"
    )

    legacy_tools = law_tools if LLM_TOOL_LOOP_ENABLED else []
    if not LLM_TOOL_LOOP_ENABLED:
        print(
            "  [LLM-TOOL-LOOP] legacy mode disabled by LLM_TOOL_LOOP_ENABLED=false; "
            "Gemini receives no function tools.",
            flush=True,
        )

    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT + date_instruction,
        tools=legacy_tools,
        temperature=0.1,  # 법률 도메인 — 강제 규칙 준수 + 사실 기반 답변 (0.0에 가까울수록 결정적)
        thinking_config=_thinking_config_for(GEMINI_COMPLEX_THINKING_BUDGET),
    )

    # Function calling 루프 (최대 8회 — 병렬 호출 + 6회차 마무리 강제)
    for loop_i in range(6):  # 병렬 호출 도입으로 6회면 12~18개 도구 실행 가능
        # 429 에러 자동 재시도 (무료 티어 분당 제한 대응)
        response = None
        last_err = None
        for retry in range(3):
            try:
                response = client.models.generate_content(
                    model=MODEL_ID,
                    contents=contents,
                    config=config,
                )
                break  # 성공
            except Exception as api_err:
                last_err = api_err
                err_msg = str(api_err)
                if any(kw in err_msg for kw in ["429", "RESOURCE_EXHAUSTED", "503", "UNAVAILABLE"]):
                    import time
                    wait_sec = 2 * (retry + 1)  # 2/4/6초 (기존 15/30/45초→2/4/6초)
                    print(f"  [API] Retry {retry+1}/3 - waiting {wait_sec}s...")
                    time.sleep(wait_sec)
                else:
                    raise  # 429 외 에러는 그대로 전달
        
        if response is None:
            raise last_err or Exception("API call failed after 3 retries")

        # Function call 응답인지 확인
        candidate = response.candidates[0]
        
        # content가 None인 경우 (안전 필터 또는 빈 응답)
        if candidate.content is None or not candidate.content.parts:
            reason = getattr(candidate, 'finish_reason', None)
            print(f"  [WARNING] Empty response. finish_reason={reason}")
            if reason and "SAFETY" in str(reason):
                return "⚠️ 해당 질문은 AI 안전 정책에 의해 답변이 제한됩니다. 계약·조달 관련 법률 질문으로 다시 시도해 주세요.", history
            elif reason and "RECITATION" in str(reason):
                return "⚠️ 법령 원문 인용 제한으로 답변이 생성되지 않았습니다. 질문을 좀 더 구체적으로 입력해 주세요.", history
            elif reason and "STOP" in str(reason) and loop_i < 5:
                print("  [RETRY] Empty STOP -> Forcing final answer generation")
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_text(text="시스템 오류로 인해 앞서 작성하신 답변 내용이 지워졌습니다. 검색된 법령/지침 조항과 업체 정보 등을 빠짐없이 포함하여, 처음부터 끝까지 완전하고 구체적인 최종 답변을 마크다운 형식으로 다시 한 번 작성해주세요.")]
                    )
                )
                continue
            else:
                return "⚠️ 답변을 생성하지 못했습니다. 질문을 계약·조달 법령과 관련된 구체적인 내용으로 다시 작성해 주세요.\n\n예시: \"수의계약 기준 금액이 얼마야?\", \"지역제한 입찰 가능한 조건이 뭐야?\"", history
        
        has_function_call = False

        # 모든 function_call을 수집
        function_calls = []
        for part in candidate.content.parts:
            if part.function_call:
                has_function_call = True
                function_calls.append(part.function_call)

        if function_calls:
            # 모델 응답을 대화에 추가 (1회만)
            contents.append(candidate.content)

            # 병렬 실행: 여러 도구를 동시에 호출
            if len(function_calls) > 1:
                print(f"  [PARALLEL] {len(function_calls)}개 도구 병렬 실행!")
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=len(function_calls)) as pool:
                    futures = {}
                    for idx, fc in enumerate(function_calls):
                        print(f"  [tool] {fc.name}({dict(fc.args) if fc.args else {}})")
                        if progress_callback:
                            label = TOOL_LABELS.get(fc.name, "🔍 검색 중")
                            query = dict(fc.args).get("query", "") if fc.args else ""
                            progress_callback(f"{label}: {query}" if query else label)
                        call_key = f"{idx}:{fc.name}"
                        futures[call_key] = (fc, pool.submit(_execute_function_call, fc))

                    # 결과 수집 → 한 번에 전송
                    response_parts = []
                    for call_key, (fc, future) in futures.items():
                        try:
                            result_str = future.result(timeout=35)
                        except Exception as e:
                            result_str = json.dumps({"error": str(e)}, ensure_ascii=False)
                        llm_result_str, _, _ = _build_llm_tool_response(fc, result_str)
                        response_parts.append(
                            types.Part.from_function_response(
                                name=fc.name,
                                response={"result": llm_result_str}
                            )
                        )
                    contents.append(types.Content(role="user", parts=response_parts))
            else:
                # 단일 호출
                fc = function_calls[0]
                print(f"  [tool] {fc.name}({dict(fc.args) if fc.args else {}})")
                if progress_callback:
                    label = TOOL_LABELS.get(fc.name, "🔍 검색 중")
                    query = dict(fc.args).get("query", "") if fc.args else ""
                    progress_callback(f"{label}: {query}" if query else label)
                result_str = _execute_function_call(fc)
                contents.append(
                    types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=fc.name,
                            response={"result": _build_llm_tool_response(fc, result_str)[0]}
                        )]
                    )
                )

        if not has_function_call:
            # 최종 텍스트 답변
            answer = candidate.content.parts[0].text if candidate.content.parts else ""

            # ─── 환각 방지: verify_citations ───
            if progress_callback:
                progress_callback("✅ 법령 인용 검증 중...")
            answer = _verify_and_annotate(answer)

            # 대화 이력 업데이트
            history.append({"role": "user", "text": user_message})
            history.append({"role": "model", "text": answer})

            global _last_generation_meta
            _last_generation_meta = {
                "prompt_mode": "legacy",
                "candidate_table_source": "none",
                "legal_conclusion_allowed": False,
                "final_answer_scanned": True,
                "model_used": MODEL_ID,
                "llm_payload_tool_count_available": len(legacy_tools[0].function_declarations) if legacy_tools else 0,
                "llm_tool_loop_enabled": LLM_TOOL_LOOP_ENABLED,
                "llm_internal_tools_disabled": not LLM_TOOL_LOOP_ENABLED,
            }

            return answer, history

    print(f"  [WARNING] Function calling loop exhausted after {loop_i+1} iterations")
    return "⚠️ 법령 검색 반복 한도를 초과했습니다. 질문을 더 구체적으로(예: 기관 유형 명시) 입력해 주세요.", history



# ─────────────────────────────────────────────
# v1.4.4 Dynamic Prompt Pipeline
# ─────────────────────────────────────────────

def _verify_and_annotate_v144(answer: str, tool_results: list[dict]) -> str:
    """
    승인 조건 3번: 최종 답변의 법령 인용을 MCP 결과와 대조.
    P0-9: 법령명+조문 단위로 검증. 다른 법령의 같은 조문번호를 오판하지 않음.
    """
    # MCP에서 확인된 법령 근거 수집 — 법령명+조문 쌍
    verified_law_articles = set()  # ("지방계약법", "제25조") 형태
    verified_articles_only = set()  # "제25조" 형태 (법령명 없을 때 fallback)

    # 법령명 패턴: ~법, ~령, ~규칙, ~기준, ~규정, ~조례
    law_name_pattern = r'[가-힣]+(?:법|령|규칙|기준|규정|조례)(?:\s*시행[령규칙])?'
    article_pattern = r'제\d+조(?:의\d+)?'

    for r in tool_results:
        if r.get("status") == "success":
            text = str(r.get("result", ""))
            # 법령명 + 조문 쌍 추출
            for m in re.finditer(f'({law_name_pattern})\\s*({article_pattern})', text):
                law_name = m.group(1).strip()
                article = m.group(2)
                verified_law_articles.add((law_name, article))
                verified_articles_only.add(article)
            # 법령명 없이 조문만 나오는 경우도 수집
            for m in re.findall(article_pattern, text):
                verified_articles_only.add(m)

    # 답변에서 법령 인용을 줄 단위로 검증
    combined_pattern = re.compile(law_name_pattern + r'\s*' + article_pattern)
    lines = answer.split("\n")
    new_lines = []
    for line in lines:
        if "[최신 법령 확인 완료]" in line:
            # 해당 줄에서 법령명+조문 쌍 추출
            found_pairs = []
            for m in combined_pattern.finditer(line):
                full = m.group(0)
                ln_m = re.match(law_name_pattern, full)
                art_m = re.search(article_pattern, full)
                if ln_m and art_m:
                    found_pairs.append((ln_m.group(0).strip(), art_m.group(0)))
            articles_only = re.findall(article_pattern, line)
            is_verified = True

            if found_pairs:
                for law_name, article in found_pairs:
                    if (law_name, article) not in verified_law_articles:
                        is_verified = False
                        break
            elif articles_only:
                for art in articles_only:
                    if art not in verified_articles_only:
                        is_verified = False
                        break

            if not is_verified:
                line = line.replace("[최신 법령 확인 완료]", "[확인 필요]")
        new_lines.append(line)
    answer = "\n".join(new_lines)

    # verify_citations MCP 도구 호출 시도
    try:
        result = mcp.verify_citations(answer)
        if result and "HALLUCINATION_DETECTED" in result:
            # 환각 감지 시 경고 추가
            answer += "\n\n⚠️ 일부 법령 인용의 정확성을 확인하지 못했습니다. 법제처 법령정보센터에서 원문을 재확인해 주세요."
    except Exception:
        pass  # verify_citations 실패 시 위의 로컬 검증만 사용

    return answer




def _extract_item_keyword(msg):
    synonym_query = extract_item_keyword_with_synonyms(msg)
    if _is_specific_item_keyword(synonym_query):
        return synonym_query

    import re
    # 알려진 주요 품목 명시적 추출
    # (매칭 패턴, API 검색어) — 순서 중요: 긴 패턴 우선
    known_products = [
        ("LED조명", "LED 조명"), ("LED 조명", "LED 조명"), ("LED", "LED 조명"),
        ("CCTV", "CCTV"), ("컴퓨터", "컴퓨터"), ("공기청정기", "공기청정기"),
        ("드론", "드론"), ("노트북", "노트북"), ("책상", "책상"), ("의자", "의자"),
        ("프린터", "프린터"), ("모니터", "모니터"), ("서버", "서버"),
        ("수중펌프", "수중펌프"), ("펌프수문", "펌프수문"), ("안전펜스", "안전펜스"),
        ("에어컨", "에어컨"), ("복사기", "복사기"), ("가구", "가구"),
        ("차량", "차량"), ("냉난방기", "냉난방기"), ("소방설비", "소방설비"),
        ("정수기", "정수기"), ("복합기", "복합기"), ("칠판", "칠판"),
        ("전자칠판", "전자칠판"), ("빔프로젝터", "빔프로젝터"),
    ]
    for pattern, api_query in known_products:
        if pattern.lower() in msg.lower():
            return api_query

    # 불용어와 서술어를 정규식으로 제거 (금액, 서술어 등)
    pattern = r'(부산\s*업체|지역\s*업체|업체|추천.*|찾아.*|검색.*|알려.*|어딨.*|뭐야|부탁.*|요청.*|어떤.*|있.*|어디.*|가급적.*|계약.*|방법.*|할\s*수.*|싶.*|\?|!|\.|\d+천만원으로|\d+만원으로|\d+억원으로|\d+만원|\d+천만원|구매해야\s*한다|구매.*)'
    res = re.sub(pattern, '', msg).strip()
    # 조사 제거
    res = re.sub(r'(은|는|이|가|을|를|로|으로|랑|하고)$', '', res).strip()
    return res

def _execute_tier_0_fast_track(user_message: str, history: list, api_status, progress_callback=None, intent_labels: list = None) -> tuple[str, list]:
    import time
    import json
    import re
    import app.company_api as company_api
    from policies.candidate_policy import classify_candidates, get_candidate_counts
    from policies.candidate_formatter import format_candidate_tables

    start_time = time.time()
    if not intent_labels:
        intent_labels = []
        
    if progress_callback:
        progress_callback("⚡ [Tier 0] 초고속 지역업체 검색 중...")
        
    query = _extract_item_keyword(user_message)
    if not query:
        query = user_message # fallback
        
    all_tool_results = []
    called_tools_list = []
    source_call_statuses = {}
    
    def _run_tool(tool_name: str, func, *, tool_args: dict = None, **kwargs):
        _tool_args = tool_args if tool_args is not None else {}
        tool_start = time.time()
        try:
            raw_res = func(**kwargs)
            status = "success"
            if isinstance(raw_res, dict) and "error" in raw_res:
                status = "failed"
        except Exception as e:
            raw_res = {"error": str(e)}
            status = "failed"
            
        elapsed = int((time.time() - tool_start) * 1000)
        all_tool_results.append({
            "tool_name": tool_name,
            "status": status,
            "result": json.dumps(raw_res, ensure_ascii=False),
            "elapsed_ms": elapsed,
            "tool_args": _tool_args
        })
        called_tools_list.append(tool_name)
        source_call_statuses[tool_name] = status
        return raw_res

    # Intent -> API mapping logic
    is_detail_view = False
    detail_data = None

    if "company_detail" in intent_labels:
        match = re.search(r'[a-fA-F0-9]{32}', user_message)
        if match:
            company_id = match.group(0)
            detail_data = _run_tool("get_company_detail", company_api.get_company_detail,
                                    tool_args={"company_id": company_id}, company_id=company_id)
            is_detail_view = True
        else:
            _run_tool("search_company_by_product", company_api.search_by_product,
                      tool_args={"query": query}, query=query)
    elif "policy_candidate_search" in intent_labels:
        # 정책기업 매핑 정보를 tool_args에 명시적으로 기록
        from company_api import POLICY_ALIAS_MAP
        mapped_subtype = POLICY_ALIAS_MAP.get(user_message.strip(), user_message.strip())
        # 키워드에서 정책 유형 추출 시도
        for kor_key, eng_val in POLICY_ALIAS_MAP.items():
            if kor_key in user_message:
                mapped_subtype = eng_val
                break
        pol_res = _run_tool("search_company_by_policy", company_api.search_by_policy,
                            tool_args={"raw_query": user_message, "mapped_policy_subtype": mapped_subtype, "query": query},
                            query=user_message)
        prod_res = _run_tool("search_company_by_product", company_api.search_by_product,
                             tool_args={"query": query}, query=query)
        
        pol_cands = pol_res.get("data", pol_res.get("candidates", [])) if isinstance(pol_res, dict) else []
        prod_cands = prod_res.get("data", prod_res.get("candidates", [])) if isinstance(prod_res, dict) else []
        
        pol_ids = {c.get("company_id") for c in pol_cands if isinstance(c, dict) and c.get("company_id")}
        intersected = [c for c in prod_cands if isinstance(c, dict) and c.get("company_id") in pol_ids]
        
        intersected_result = {
            "candidates": intersected,
            "meta": pol_res.get("meta", {}) if isinstance(pol_res, dict) else {}
        }
        # 기존 tool_args_log 보존
        _preserved_args = [tr.get("tool_args", {}) for tr in all_tool_results]
        all_tool_results = [{
            "tool_name": "intersected_policy_product_search",
            "status": "success",
            "result": json.dumps(intersected_result, ensure_ascii=False),
            "elapsed_ms": sum(r["elapsed_ms"] for r in all_tool_results),
            "tool_args": {"raw_query": user_message, "mapped_policy_subtype": mapped_subtype, "product_query": query,
                          "sub_tool_args": _preserved_args}
        }]
    elif "certified_product_search" in intent_labels:
        if "혁신" in user_message:
            _run_tool("search_innovation_product", company_api.search_innovation_product,
                      tool_args={"product_name": query}, product_name=query)
        elif "우수" in user_message:
            _run_tool("search_excellent_procurement_product", company_api.search_excellent_procurement_product,
                      tool_args={"product_name": query}, product_name=query)
        else:
            _run_tool("search_certified_product", company_api.search_certified_product,
                      tool_args={"product_name": query}, product_name=query)
    elif "shopping_mall_search" in intent_labels or "mas_shopping_mall" in intent_labels:
        _run_tool("search_shopping_mall_product", company_api.search_shopping_mall_product,
                  tool_args={"product_name": query}, product_name=query)
    else:
        _run_tool("search_company_by_product", company_api.search_by_product,
                  tool_args={"query": query}, query=query)

    def _get_detail_field(d_dict, *keys, default="알 수 없음"):
        """Multi-key fallback: 여러 후보 키 중 첫 번째 유효한 값 반환."""
        for k in keys:
            v = d_dict.get(k)
            if v and v != "알 수 없음" and v != "unknown":
                if isinstance(v, list):
                    return ", ".join(str(x) for x in v) if v else default
                return str(v)
        return default

    if is_detail_view and detail_data:
        classified = {}
        counts = {}
        # API 응답 구조: {meta, candidates: [...]} → candidates[0]에서 실제 데이터 추출
        _raw = detail_data
        if isinstance(_raw, dict):
            _cands = _raw.get("candidates", [])
            if _cands and isinstance(_cands, list) and len(_cands) > 0:
                d = _cands[0]
            else:
                d = _raw.get("data", _raw)
        else:
            d = _raw
        
        if not isinstance(d, dict) or "error" in d:
            formatted = ""
        else:
            lines = ["### 🏢 업체 상세 정보"]
            lines.append(f"- **업체명**: {_get_detail_field(d, 'company_name', '업체명', 'name')}")
            lines.append(f"- **소재지**: {_get_detail_field(d, 'detail_address', 'address', 'company_address', '주소', '소재지', 'location')}")
            lines.append(f"- **주요품목**: {_get_detail_field(d, 'main_products', 'products', '대표품목', 'items')}")
            # 면허/업종
            lic = d.get('license_or_business_type', [])
            if lic and isinstance(lic, list):
                lines.append(f"- **면허/업종**: {', '.join(str(x) for x in lic)}")
            # 영업상태
            biz_status = d.get('business_status', 'unknown')
            biz_freshness = d.get('business_status_freshness', '')
            if biz_status and biz_status != 'unknown':
                status_label = f"{biz_status}"
                if biz_freshness:
                    status_label += f" ({biz_freshness})"
                lines.append(f"- **영업상태**: {status_label}")
            # 후보유형
            c_types = d.get('candidate_types', [])
            if c_types and isinstance(c_types, list):
                lines.append(f"- **후보유형**: {', '.join(str(t) for t in c_types)}")
            # 정책기업
            policy_subs = d.get('policy_subtypes', d.get('policy_tags', []))
            if policy_subs and isinstance(policy_subs, list) and len(policy_subs) > 0:
                lines.append(f"- **정책기업**: {', '.join(str(t) for t in policy_subs)}")
            # 쇼핑몰 플래그
            mall_flags = d.get('shopping_mall_flags', [])
            if mall_flags and isinstance(mall_flags, list):
                lines.append(f"- **쇼핑몰 등록**: {', '.join(str(f) for f in mall_flags)}")
            # 인증제품
            cert_types = d.get('certified_product_types', [])
            if cert_types and isinstance(cert_types, list) and len(cert_types) > 0:
                lines.append(f"- **인증제품**: {', '.join(str(t) for t in cert_types)}")
            # 중소기업 직접생산
            sme = d.get('sme_competition_product')
            if sme:
                lines.append(f"- **중소기업간 경쟁제품**: 해당")
            # 디버그: API 응답에 존재하는 실제 키를 generation_meta에 기록
            _detail_api_keys = list(d.keys()) if isinstance(d, dict) else []
            formatted = "\n".join(lines)
            
        candidate_table_source = "server_structured_formatter" if formatted else "none"
    else:
        classified = classify_candidates(all_tool_results, user_message)
        counts = get_candidate_counts(classified)
        route_candidate_options = _route_candidate_display_options_for_answer(user_message, all_tool_results)
        formatted = format_candidate_tables(classified, user_message, "", **route_candidate_options)
        candidate_table_source = "server_structured_formatter" if formatted else "none"
        _detail_api_keys = []

    # tool_elapsed_ms_by_name 집계
    _tool_elapsed_by_name = {}
    for _tr in all_tool_results:
        _tn = _tr.get("tool_name", "unknown")
        _tool_elapsed_by_name[_tn] = _tool_elapsed_by_name.get(_tn, 0) + _tr.get("elapsed_ms", 0)

    # tool_args_log 생성
    _tool_args_log = [{"tool": _tr["tool_name"], "args": _tr.get("tool_args", {})} for _tr in all_tool_results]

    generation_meta = {
        "model_used": "bypass_tier_0",
        "model_decision_reason": "Tier 0 (Fast Track): LLM 및 MCP 전면 우회",
        "tier_resolved": 0,
        "fast_track_applied": True,
        "deterministic_template_used": True,
        "company_table_allowed": True,
        "legal_conclusion_allowed": False,
        "contract_possible_auto_promoted": False,
        "mcp_chain_executed": False,
        "candidate_table_source": candidate_table_source,
        "answer_schema_version": "simplified_company_search_v1",
        "source_status": "no_mcp_required",
        "rag_elapsed_ms": 0,
        "mcp_status": "not_called",
        "model_elapsed_ms": 0,
        "mcp_preflight_elapsed_ms": 0,
        "called_tools": called_tools_list,
        "source_call_statuses": source_call_statuses,
        "company_search_status": "success" if formatted else "no_results",
        "classified_candidate_count": sum(counts.values()) if not is_detail_view else (1 if formatted else 0),
        "formatter_input_count": sum(counts.values()) if not is_detail_view else (1 if formatted else 0),
        "formatter_output_chars": len(formatted) if formatted else 0,
        "tool_call_count": len(all_tool_results),
        "tool_elapsed_ms_by_name": _tool_elapsed_by_name,
        "tool_args_log": _tool_args_log,
        "detail_api_response_keys": _detail_api_keys if is_detail_view else [],
        "company_search_query": query,
    }

    if is_detail_view:
        template = (
            "### 1. 질문의도 파악\n"
            "- 특정 업체 상세정보 조회 요청입니다.\n\n"
            f"{formatted}\n\n"
            "### 3. 확인 필요사항\n"
            "- 관리ID(company_id)는 상세조회용 내부 식별자이며 사업자등록번호가 아닙니다.\n"
            "- 상세조회 정보는 정책적격성을 최종 판단하는 법적 효력이 없으므로 반드시 원본 서류를 확인하세요.\n"
        ) if formatted else (
            "⚠️ 해당 ID의 업체 정보를 찾을 수 없거나 조회가 실패했습니다."
        )
    else:
        from policies.answer_builder_policy import build_simple_company_search_answer
        template = build_simple_company_search_answer(generation_meta, has_candidates=bool(formatted))
        generation_meta.update(counts)
        generation_meta["candidate_counts_by_type"] = {
            "local_procurement_company": counts.get("local_company_count", 0),
            "shopping_mall_supplier": counts.get("mall_company_count", 0),
            "policy_company": counts.get("primary_policy_company_count", 0),
            "innovation_product": counts.get("innovation_product_count", 0),
            "priority_purchase_product": counts.get("priority_purchase_count", 0),
        }
    
    api_status.mcp_status = "not_called"
    api_status.law_api_status = "not_called"
    api_status.company_search_status = "success" if formatted else "not_called"
    
    answer, updated_history = _finalize_answer(
        answer=template,
        history=history,
        user_message=user_message,
        all_tool_results=all_tool_results,
        api_status=api_status,
        progress_callback=progress_callback,
        generation_meta=generation_meta
    )
    return answer, updated_history

# ─── MCP 실패 응답 공통 판정 함수 ───
_MCP_FAILURE_MARKERS = [
    "error", "warning", "timeout", "timed out", "read timed out",
    "connecttimeout", "readtimeout", "connectionerror",
    "max retries exceeded", "mcp 호출 오류", "api 오류",
    "응답 지연", "시간 초과", "호출 시간 초과", "[timeout]", "[failed]",
]

def is_mcp_error(res_str: str) -> bool:
    """MCP 응답이 실패인지 판정한다.
    1) JSON 파싱을 먼저 수행하여 구조적 에러를 감지한다.
    2) 이후 known failure marker 기반 문자열 검사를 수행한다.
    """
    if not res_str or not res_str.strip():
        return True
    # 1. JSON 구조 검사
    try:
        import json as _json_check
        parsed = _json_check.loads(res_str)
        if isinstance(parsed, dict):
            if "error" in parsed or "warning" in parsed:
                return True
            if parsed.get("success") is False:
                return True
            status_val = str(parsed.get("status", "")).lower()
            if status_val in ("timeout", "failed", "error"):
                return True
    except (ValueError, TypeError):
        pass
    # 2. Known failure marker 문자열 검사
    lower = res_str.lower()
    for marker in _MCP_FAILURE_MARKERS:
        if marker in lower:
            return True
    return False

_MCP_FAILED_PLACEHOLDER = "[MCP_FAILED] 해당 근거는 조회 실패로 법적 판단 근거에서 제외됨"

class MockFunctionCall:
    def __init__(self, name, args):
        self.name = name
        self.args = args

def _execute_tier_2_mandatory_mcp(user_message: str, plan: list, progress_callback=None) -> tuple[str, list, list, list, dict]:
    import concurrent.futures
    import json
    import time

    executed = []
    missing = []
    raw_results = []
    evidence_cards = []
    
    cache_stats = {
        "legal_basis_cache_used": True,
        "legal_basis_cache_hit_count": 0,
        "legal_basis_cache_miss_count": 0,
        "mcp_called_for_cache_miss": False,
        "mcp_called_for_freshness": False,
        "cache_status": "enabled",
        "evidence_cards": [],
        "evidence_card_count": 0,
        "internal_db_hit_count": 0,
        "external_mcp_fallback_count": 0,
        "evidence_missing_count": 0,
    }
    
    if progress_callback:
        progress_callback("⚖️ [Tier 1/2] 사전 필수 법령/매뉴얼 조회 중...")

    def fetch_mcp(tool_req):
        tool_name = tool_req["name"]
        args = tool_req["args"]
        selected_reason = tool_req.get("selected_reason", "mandatory_preflight")
        cache_key = f"{tool_name}_{json.dumps(args, sort_keys=True)}"
        tool_arg_label = args.get("query") or args.get("law_name") or args.get("lawName") or args.get("mst") or args.get("rule_id") or ""
        tool_key = f"{tool_name}:{tool_arg_label}"
        
        if cache_key in _mcp_cache:
            return tool_key, tool_name, args, selected_reason, _mcp_cache[cache_key], True, 0
            
        start_time = time.time()
        try:
            mock_fc = MockFunctionCall(tool_name, args)
            res_str = _execute_function_call(mock_fc)
            elapsed_ms = int((time.time() - start_time) * 1000)
            
            # is_mcp_error 기반 판정: 실패 응답은 캐시에 저장하지 않음
            if is_mcp_error(res_str):
                return tool_key, tool_name, args, selected_reason, res_str, False, elapsed_ms
            _mcp_cache[cache_key] = res_str
            return tool_key, tool_name, args, selected_reason, res_str, False, elapsed_ms
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return tool_key, tool_name, args, selected_reason, f"Error: {e}", False, elapsed_ms

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(fetch_mcp, req) for req in plan]
        for future in concurrent.futures.as_completed(futures):
            tool_key, tool_name, args, selected_reason, res_str, from_cache, elapsed_ms = future.result()
            
            if from_cache:
                cache_stats["legal_basis_cache_hit_count"] += 1
                executed.append(f"{tool_key} (cache_hit)")
            else:
                cache_stats["legal_basis_cache_miss_count"] += 1
                cache_stats["mcp_called_for_cache_miss"] = True
                
                # is_mcp_error 기반 판정: 실패 시 missing, 성공 시 executed
                if is_mcp_error(res_str):
                    missing.append(f"{tool_key} (failed)")
                else:
                    executed.append(f"{tool_key} ({elapsed_ms}ms)")
                
            # 실패 응답은 LLM context에 안전 placeholder로 대체
            if is_mcp_error(res_str) and not from_cache:
                raw_results.append(f"[{tool_key}]\n{_MCP_FAILED_PLACEHOLDER}")
            else:
                raw_results.append(f"[{tool_key} (Cache: {from_cache})]\n{res_str}")

            try:
                from policies.legal_evidence_cards import build_evidence_card

                evidence_cards.append(build_evidence_card(
                    tool_name=tool_name,
                    args=args,
                    result=res_str,
                    from_cache=from_cache,
                    elapsed_ms=elapsed_ms,
                    selected_reason=selected_reason,
                ))
            except Exception as e:
                print(f"  [EVIDENCE-CARD] build skipped: {e}", flush=True)
            
    try:
        from policies.legal_evidence_cards import render_evidence_card_context, render_evidence_context, summarize_evidence_counts

        evidence_max_cards = _env_int_value("EVIDENCE_CONTEXT_MAX_CARDS", 14)
        evidence_excerpt_chars = _env_int_value("EVIDENCE_CONTEXT_EXCERPT_CHARS", 450)
        evidence_summary = render_evidence_context(evidence_cards, max_cards=evidence_max_cards)
        card_context = render_evidence_card_context(
            evidence_cards,
            max_cards=evidence_max_cards,
            excerpt_limit=evidence_excerpt_chars,
        )
        cache_stats.update(summarize_evidence_counts(evidence_cards))
        cache_stats["evidence_cards"] = evidence_cards
        cache_stats["mcp_context_card_max_cards"] = evidence_max_cards
        cache_stats["mcp_context_card_excerpt_chars"] = evidence_excerpt_chars
        raw_context = "\n\n".join(([evidence_summary] if evidence_summary else []) + raw_results)
        selected_context, context_meta = _select_evidence_context(
            raw_context=raw_context,
            card_context=card_context,
            mode=_evidence_context_mode("EVIDENCE_CONTEXT_MODE"),
            prefix="mcp_context",
            cards=evidence_cards,
        )
        cache_stats.update(context_meta)
        cache_stats["evidence_context_card_excerpts_included"] = bool(card_context)
        print(
            "  [EVIDENCE-CONTEXT] "
            f"mode={context_meta.get('mcp_context_mode_applied')} "
            f"raw={context_meta.get('mcp_context_raw_chars')} "
            f"card={context_meta.get('mcp_context_card_chars')} "
            f"llm={context_meta.get('mcp_context_llm_chars')} "
            f"savings={context_meta.get('mcp_context_char_savings_pct')}%",
            flush=True,
        )
        return selected_context, plan, executed, missing, cache_stats
    except Exception as e:
        print(f"  [EVIDENCE-CARD] summarize skipped: {e}", flush=True)

    mcp_context = "\n\n".join(raw_results)
    cache_stats.update({
        "mcp_context_mode_requested": _evidence_context_mode("EVIDENCE_CONTEXT_MODE"),
        "mcp_context_mode_applied": "raw_fallback_card_build_failed",
        "mcp_context_comparison_enabled": True,
        "mcp_context_raw_chars": len(mcp_context),
        "mcp_context_card_chars": 0,
        "mcp_context_llm_chars": len(mcp_context),
        "mcp_context_card_to_raw_ratio": 0.0,
        "mcp_context_char_savings_pct": 0.0,
        "mcp_context_card_hit_count": 0,
        "mcp_context_card_miss_count": 0,
    })
    return mcp_context, plan, executed, missing, cache_stats


def _should_use_grounded_single_pass_llm(user_message: str, query_tier: int, amount_detected, route_plan=None) -> bool:
    """Use a short DB-grounded LLM pass for real amount/case questions.

    This keeps deterministic templates narrow while avoiding the full function-calling
    loop for common questions such as "2억 물품 수의계약 가능해?".
    """
    if route_plan is not None:
        if not _route_plan_needs(route_plan, "legal_basis"):
            return False
    elif query_tier not in (1, 2):
        return False

    q = (user_message or "").replace(" ", "").lower()
    has_contract_method = any(term in q for term in ("수의계약", "1인견적", "견적", "입찰", "지역제한"))
    has_contract_object = any(term in q for term in ("물품", "용역", "공사", "구매", "사려", "살건데", "납품"))
    asks_case_judgment = any(term in q for term in (
        "가능", "될까", "되나", "해도", "살건데", "사려",
        "살수있", "할수있", "할수있어", "살수있어",
    ))
    needs_company_lookup = any(term in q for term in ("부산업체", "지역업체", "업체추천", "후보", "찾아", "검색"))

    if amount_detected is not None:
        return has_contract_method and has_contract_object and asks_case_judgment and not needs_company_lookup

    industry_legal_terms = (
        "전기공사", "정보통신공사", "통신공사", "소프트웨어", "sw",
        "소프트웨어사업", "건설공사", "건설업", "건설사업관리",
        "소방공사", "소방시설",
    )
    asks_industry_legal_review = any(term in q for term in industry_legal_terms) and any(term in q for term in (
        "분리발주", "분리도급", "기술성평가", "평가기준", "발주기준",
        "관련법령", "근거", "기준", "설명", "검토", "해야", "가능", "여부",
    ))
    return asks_industry_legal_review and not needs_company_lookup


def _generate_grounded_single_pass_answer(user_message: str, mcp_context: str, agency_type: str | None, timeout_sec: int = 25) -> str | None:
    """Generate one LLM answer from internal law/admin-rule context, without tools."""
    import concurrent.futures
    global _current_llm_payload_meta

    agency_label = agency_type or "미지정"
    answer_budget, answer_budget_reason = _answer_thinking_budget_for(
        user_message,
        base_budget=GEMINI_GROUNDED_THINKING_BUDGET,
    )
    _current_llm_payload_meta["llm_answer_thinking_budget"] = answer_budget
    _current_llm_payload_meta["llm_answer_thinking_budget_reason"] = answer_budget_reason
    print(
        f"  [ANSWER-BUDGET] grounded budget={answer_budget} reason={answer_budget_reason}",
        flush=True,
    )
    prompt = f"""
당신은 공공계약 담당자를 돕는 실무형 법령 상담 챗봇입니다.

[중요 원칙]
- 아래 [내부 DB 근거]에 있는 내용만 사용하세요.
- 도구 호출, 외부 검색, 업체 후보 생성은 하지 마세요.
- 금액 기준, 수의계약 가능 여부, 1인 견적 가능 여부를 구분하세요.
- 근거가 부족한 예외사유는 만들지 말고 "추가 확인 필요"라고 하세요.
- 답변은 5~8문장 정도로 간결하게 작성하세요.
- "가능합니다", "불가능합니다", "바로 가능합니다"처럼 단정적인 문구 대신 "검토 범위에 들어갑니다", "일반 기준만으로는 어렵습니다", "조건 충족 여부 확인이 필요합니다"처럼 쓰세요.
- 마지막에는 지역상품 구매 지원 관점의 다음 검토 경로를 한 문단으로 붙이세요.

[소속기관]
{agency_label}

[사용자 질문]
{user_message}

[내부 DB 근거]
{mcp_context[:12000]}
""".strip()

    def _call_model():
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1200,
                thinking_config=_thinking_config_for(answer_budget),
            ),
        )
        return response.text.strip() if getattr(response, "text", None) else None

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = executor.submit(_call_model)
    try:
        return future.result(timeout=timeout_sec)
    except Exception as e:
        print(f"  [GROUNDED-LLM] skipped: {type(e).__name__}: {e}", flush=True)
        future.cancel()
        return None
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _build_grounded_case_timeout_fallback(user_message: str, mcp_context: str = "") -> str:
    """Short fallback when DB was read but the one-pass LLM call is delayed."""
    q = (user_message or "").replace(" ", "")
    context = mcp_context or ""
    if ("정보통신공사" in q or "통신공사" in q) and "분리발주" in q:
        return "\n".join([
            "내부 DB 근거 기준으로 요약하면 다음과 같습니다.",
            "",
            "정보통신공사는 원칙적으로 건설공사·전기공사 등 다른 공사와 분리하여 도급하는 기준을 먼저 검토해야 합니다.",
            "근거: 「정보통신공사업법」 제25조는 공사를 다른 공사와 분리하여 도급하도록 정하고, 공사의 성질상 또는 기술관리상 분리 도급이 곤란한 경우 예외를 둘 수 있다고 규정합니다.",
            "",
            "실무적으로는 발주 설계서에서 정보통신공사 범위가 별도로 산정되는지, 예외사유가 있는지, 관련 시행령상 예외 요건에 해당하는지를 먼저 확인하는 흐름이 안전합니다.",
        ])
    if "전기공사" in q and "분리발주" in q:
        return "\n".join([
            "내부 DB 근거 기준으로 요약하면 다음과 같습니다.",
            "",
            "전기공사는 원칙적으로 다른 업종의 공사와 분리발주하는 기준을 먼저 검토해야 합니다.",
            "근거: 「전기공사업법」 제11조는 전기공사 및 시공책임형 전기공사관리를 다른 업종의 공사와 분리발주하도록 정하고, 긴급복구·기밀 유지·기술관리상 곤란한 경우 등 예외를 둡니다.",
            "",
            "실무적으로는 공사 내역서에서 전기공사 범위를 분리 산정하고, 예외 적용이 필요한 경우 사유를 문서화하는 방향이 안전합니다.",
        ])
    if ("소프트웨어" in q or "SW" in (user_message or "").upper()) and ("기술성평가" in q or "기술성" in q):
        return "\n".join([
            "내부 DB 근거 기준으로 요약하면 다음과 같습니다.",
            "",
            "소프트웨어 용역은 가격만으로 판단하기보다 기술성 평가 기준을 함께 적용하는 구조를 검토해야 합니다.",
            "근거: 「소프트웨어 진흥법」 제49조는 국가기관등의 소프트웨어사업 계약과 기술성 평가 기준 적용을 규정하고, 세부 기준은 「소프트웨어 기술성 평가기준 지침」 및 「소프트웨어사업 계약 및 관리감독에 관한 지침」에서 확인해야 합니다.",
            "",
            "실무적으로는 제안요청서의 평가항목, 기술능력 평가비중, 과업심의·요구사항 명확화 여부를 함께 확인하는 것이 좋습니다.",
        ])
    if "수의계약" in q and "물품" in q:
        from policies.numeric_basis_policy import get_numeric_display, get_numeric_value
        amount = _parse_amount(user_message)
        policy_limit = get_numeric_value("P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD")
        if amount is None or not isinstance(policy_limit, (int, float)) or amount <= policy_limit:
            pass
        else:
            amount_label = _display_amount_for_answer(amount, user_message)
            general_threshold = get_numeric_display("P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD") or "기준값 확인 필요"
            policy_threshold = get_numeric_display("P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD") or "기준값 확인 필요"
            return "\n".join([
                "확인된 근거 기준으로 요약하면 다음과 같습니다.",
                "",
                f"물품 {amount_label}은 일반 물품 수의계약의 기본 소액 기준인 **추정가격 {general_threshold} 이하**를 넘습니다. 또한 정책기업 등 일부 물품ㆍ용역 수의계약 특례도 **{policy_threshold} 이하** 범위가 핵심이므로, 질문의 조건만으로는 수의계약으로 바로 진행하기 어렵습니다.",
                "",
                "다만 실제 판단은 소속기관, 추정가격 산정, 품목 특성, 여성기업ㆍ장애인기업ㆍ사회적기업 등 정책기업 해당 여부, 직접생산ㆍ조달등록 여부를 함께 확인해야 합니다.",
                "",
                "지역상품 구매 지원 관점에서는 부산 업체를 특정해 바로 수의계약으로 단정하기보다, 지역제한경쟁입찰, 2인 이상 견적, MAS/종합쇼핑몰, 직접생산ㆍ인증제품 활용 가능성을 함께 검토하는 방향이 안전합니다.",
                "근거: 「지방계약법 시행령」 제25조ㆍ제30조 및 확인된 법령·행정규칙 자료",
            ])
    if (
        any(term in q for term in ("구매", "물품", "노트북", "컴퓨터", "냉난방기", "보안용카메라", "cctv"))
        and any(term in q for term in ("1인견적", "2인견적", "견적", "종합쇼핑몰", "mas", "다수공급자"))
    ):
        from policies.numeric_basis_policy import get_numeric_display, get_numeric_value

        amount = _parse_amount(user_message)
        item_name = _extract_item_keyword(user_message) or "해당 물품"
        one_quote_general_value = get_numeric_value("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
        one_quote_policy_value = get_numeric_value("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD")
        mas_general_value = get_numeric_value("P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD")
        mas_sme_value = get_numeric_value("P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD")
        one_quote_general = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD") or "기준값 확인 필요"
        one_quote_policy = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "기준값 확인 필요"
        two_quote_threshold = get_numeric_display("P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD") or "기준값 확인 필요"
        mas_general_threshold = get_numeric_display("P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD") or "기준값 확인 필요"
        mas_sme_threshold = get_numeric_display("P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD") or "기준값 확인 필요"
        amount_label = _display_amount_for_answer(amount, user_message) if amount else "질문 금액"
        policy_fit_note = (
            "이 범위에 들어옵니다"
            if amount is not None and isinstance(one_quote_policy_value, (int, float)) and amount <= one_quote_policy_value
            else "이 범위에 들어가는지 추정가격 기준으로 확인해야 합니다"
        )
        general_one_quote_note = (
            "이를 넘습니다"
            if amount is not None and isinstance(one_quote_general_value, (int, float)) and amount > one_quote_general_value
            else "이 범위에 들어갈 수 있습니다"
        )
        mas_amount_note = "2단계 경쟁 기준은 세부품명과 금액을 함께 확인해야 합니다."
        if amount is not None and isinstance(mas_general_value, (int, float)) and isinstance(mas_sme_value, (int, float)):
            if amount < mas_general_value:
                mas_amount_note = "일반 제품 기준에도 못 미치므로 2단계 경쟁 기준 미만입니다."
            elif amount < mas_sme_value and any(term in item_name for term in ("노트북", "컴퓨터")):
                mas_amount_note = f"중소기업자간 경쟁제품 세부품명에 해당하면 기준({mas_sme_threshold}) 미만이라 2단계 경쟁 기준 미만입니다."
            else:
                mas_amount_note = "2단계 경쟁 대상 여부를 먼저 확인해야 하는 금액대입니다."

        general_section = [
            "### 1. 최우선 검토: 일반 1인 견적 소액수의",
            f"- **판단 근거**: 「지방계약법 시행령」 제25조제1항제5호 및 제30조의 견적 제출 기준을 함께 봅니다.",
            f"- **금액 기준**: 일반 1인 견적은 보통 **추정가격 {one_quote_general} 이하**가 핵심이고, 질문 금액 {amount_label}은 {general_one_quote_note}.",
            f"- **실무 의미**: 이 구간에서는 정책기업 여부가 없어도 1인 견적 가능성을 먼저 검토할 수 있습니다. 다만 부산 소재 업체 후보의 조달등록·납품 가능 품목·가격 적정성은 확인해야 합니다.",
        ]
        policy_section_primary = [
            "### 1. 최우선 검토: 여성·장애인·사회적기업 등 정책기업 1인 견적",
            f"- **판단 근거**: 「지방계약법 시행령」 제25조제1항제5호 및 제30조의 견적 제출 기준을 함께 봅니다.",
            f"- **금액 기준**: 정책기업 1인 견적은 **추정가격 {one_quote_policy} 이하**가 핵심입니다. 질문 금액 {amount_label}은 {policy_fit_note}.",
            f"- **실무 의미**: 부산 소재 여성기업·장애인기업·사회적기업 등이 실제 {item_name} 납품 가능 품목과 증빙을 갖춘 경우, 지역 내 소규모 기업을 직접 지원하는 경로로 가장 강합니다.",
        ]
        policy_section_secondary = [
            "### 2. 함께 검토: 여성·장애인·사회적기업 등 정책기업",
            f"- **금액 기준**: 질문 금액 {amount_label}은 일반 1인 견적 기준 안에 들어오면 정책기업 요건이 최우선 경로는 아닙니다.",
            f"- **실무 의미**: 그래도 부산 소재 정책기업이면 지역상품 구매와 사회적 가치 측면에서 후보 선별 기준으로 함께 볼 수 있습니다.",
        ]
        two_quote_section = [
            "### 2. 차선 검토: 지역제한 2인 이상 견적 수의계약",
            f"- **판단 근거**: 「지방계약법 시행령」 제25조제1항제5호 및 「지방자치단체 입찰 및 계약집행기준」의 수의계약 운영 기준을 확인합니다.",
            f"- **금액 기준**: 일반 1인 견적은 보통 **추정가격 {one_quote_general} 이하**가 핵심이고, 질문 금액 {amount_label}은 {general_one_quote_note}. 대신 소액수의 2인 이상 견적은 **{two_quote_threshold} 이하** 구간에서 검토합니다.",
            "- **방법**: 나라장터(G2B) 견적 제출 공고에서 부산광역시 지역제한을 설정할 수 있는지 확인합니다.",
            "- **실무 의미**: 특정 업체 지정이 부담스러우면 부산 지역 내 경쟁을 확보하면서 지역업체 낙찰 가능성을 높이는 방식입니다.",
        ]
        mas_section = [
            "### 3. 상시 검토: 나라장터 종합쇼핑몰/MAS 지역업체 필터",
            f"- **방법**: 종합쇼핑몰에서 {item_name}을 검색하고 공급업체 소재지, 납품 가능 지역, 계약상태, 규격 일치 여부를 확인합니다.",
            f"- **2단계 경쟁 기준**: 일반 제품은 **{mas_general_threshold} 이상**, 중소기업자간 경쟁제품은 **{mas_sme_threshold} 이상**일 때 2단계 경쟁 대상 여부를 봅니다.",
            f"- **실무 의미**: {item_name}이 중소기업자간 경쟁제품 세부품명에 해당하는지 먼저 확인합니다. {mas_amount_note}",
            "- **주의**: 제조사는 대기업이어도 부산 소재 공급업체·대리점이 납품대상 업체인지 확인하면 지역 매출 기여도를 높일 수 있습니다.",
        ]
        if amount is not None and isinstance(one_quote_general_value, (int, float)) and amount <= one_quote_general_value:
            route_sections = [general_section, policy_section_secondary, mas_section]
            summary_order = "일반 1인 견적 → 정책기업 후보 우선 고려 → 종합쇼핑몰/MAS 지역업체 필터"
        elif amount is not None and isinstance(one_quote_policy_value, (int, float)) and amount <= one_quote_policy_value:
            route_sections = [policy_section_primary, two_quote_section, mas_section]
            summary_order = "정책기업 1인 견적 → 부산 지역제한 2인 이상 견적 → 종합쇼핑몰/MAS 지역업체 필터"
        else:
            route_sections = [two_quote_section, mas_section]
            summary_order = "부산 지역제한 2인 이상 견적 → 종합쇼핑몰/MAS 지역업체 필터"

        parts = [
            f"### {amount_label} {item_name} 구매 경로 판단",
            f"질문 조건은 **{item_name} {amount_label} 구매**입니다. 부산 지역업체 구매 확대 관점에서는 아래 순서로 보는 것이 실무적으로 좋습니다.",
            "",
        ]
        for section in route_sections:
            parts.extend(section)
            parts.append("")
        parts.extend([
            "### 정리",
            f"**부산업체 구매 확대가 목적이면 {summary_order}** 순서로 보세요. 단, 실제 계약 전에는 추정가격 산정, 정책기업 확인서, 세부품명, 직접생산·조달등록 여부, 분할발주 위험을 확인해야 합니다.",
        ])
        return "\n".join(parts)
    return "\n".join([
        "내부 DB 근거 기준으로는 바로 단정하기 어렵습니다.",
        "질문하신 사안은 금액, 계약종류, 소속기관에 따라 결론이 달라질 수 있으므로 내부 DB 근거를 바탕으로 재시도해 주세요.",
    ])


def _build_simple_amount_contract_answer(user_message: str, amount_detected) -> str | None:
    """Fast grounded answer for common amount + direct-contract questions."""
    q = (user_message or "").replace(" ", "")
    if amount_detected is None:
        return None
    if not ("수의계약" in q and "물품" in q):
        return None

    from policies.numeric_basis_policy import get_numeric_display, get_numeric_value
    general_one_quote_value = get_numeric_value("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
    policy_one_quote_value = get_numeric_value("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD")
    policy_contract_value = get_numeric_value("P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD")
    one_quote_general = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD") or "기준값 확인 필요"
    one_quote_policy = get_numeric_display("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD") or "기준값 확인 필요"
    general_threshold = get_numeric_display("P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD") or "기준값 확인 필요"
    policy_contract = get_numeric_display("P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD") or "기준값 확인 필요"
    amount_label = _display_amount_for_answer(amount_detected, user_message)

    if (
        isinstance(policy_one_quote_value, (int, float))
        and amount_detected <= policy_one_quote_value
        and any(term in q for term in ("여성기업", "장애인기업", "사회적기업", "정책기업"))
    ):
        return "\n".join([
            "### 판단 요약",
            f"- 질문 조건이 **정책기업 물품 구매 {amount_label} 규모**라면, 확인된 기준상 정책기업 수의계약 및 1인 견적 검토 범위에 들어올 수 있습니다.",
            f"- 다만 `여성기업이라는 말만으로 계약 확정`이 아니라, 정책기업 확인서, 직접생산·품목 적합성, 추정가격 산정, 분할발주 금지 여부를 함께 확인해야 합니다.",
            "",
            "### 근거",
            f"- 정책기업 관련 물품·용역 수의계약 검토 기준: **{policy_contract} 이하**",
            f"- 정책기업 1인 견적 검토 기준: **{one_quote_policy} 이하**",
            "- 관련 근거는 「지방계약법 시행령」 제25조·제30조 및 여성기업 등 정책기업 관련 법령·행정규칙입니다.",
            "",
            "### 실무 확인사항",
            "- 여성기업확인서 등 정책기업 자격이 유효한지 확인합니다.",
            "- 구매하려는 물품이 해당 업체의 취급·직접생산·납품 가능 품목인지 확인합니다.",
            "- 부산 지역상품 구매 지원 목적이라면 부산 소재 정책기업 후보와 조달등록·종합쇼핑몰·인증 여부를 함께 조회하는 것이 좋습니다.",
        ])

    if isinstance(general_one_quote_value, (int, float)) and amount_detected <= general_one_quote_value:
        return "\n".join([
            "### 판단 요약",
            f"- 질문 조건이 **{amount_label} 물품 구매**라면, 확인된 기준상 일반 물품 소액 수의계약과 1인 견적 방식의 검토 범위에 들어옵니다.",
            "- 다만 실제 처리는 추정가격 산정, 부가가치세 포함 여부, 동일·유사 물품 분할발주 여부, 품목별 직접생산·조달등록 여부를 함께 확인한 뒤 문서화해야 합니다.",
            "",
            "### 근거",
            f"- 일반 물품·용역 수의계약 검토 기준: **추정가격 {general_threshold} 이하**",
            f"- 일반 물품·용역 1인 견적 검토 기준: **추정가격 {one_quote_general} 이하**",
            "- 관련 근거는 「지방계약법 시행령」 제25조·제30조 및 수의계약 운영 관련 행정규칙입니다.",
            "",
            "### 실무 확인사항",
            "- 질문 금액이 기준 금액과 맞닿아 있으면 추정가격 기준인지, 부가가치세 포함 총액인지 구분합니다.",
            "- 같은 물품을 기간·부서별로 나누는 구조라면 분할발주로 보일 수 있어 수요 취합과 산출근거를 남깁니다.",
            "- 부산 지역상품 구매지원 관점에서는 지역업체 후보, 종합쇼핑몰/MAS 등록, 중소기업자간 경쟁제품·직접생산확인 여부를 함께 확인하는 편이 좋습니다.",
        ])

    if isinstance(policy_contract_value, (int, float)) and amount_detected > policy_contract_value:
        return "\n".join([
            "### 판단 요약",
            f"- 질문 조건이 **지방자치단체 기준의 물품 {amount_label}**이라면, 일반적인 소액 물품 수의계약 기준만으로는 **불가에 가깝고**, 해당 방식을 바로 적용하기 어렵습니다.",
            f"- 일반 물품 수의계약은 통상 소액 기준(**{general_threshold} 이하**)과 견적 방식 제한을 먼저 확인해야 하고, 질문 금액은 정책기업 특례 기준(**{policy_contract} 이하**)도 넘는 금액대입니다.",
            "",
            "### 근거",
            "- 「지방계약법」 제9조: 원칙은 일반입찰이고, 예외적으로 지명입찰 또는 수의계약을 할 수 있습니다.",
            "- 「지방계약법 시행령」 제25조: 수의계약을 할 수 있는 예외 사유를 정합니다.",
            "- 「지방계약법 시행령」 제30조: 수의계약 대상자 선정과 견적 절차를 정합니다.",
            "",
            "### 지역상품 구매 지원 관점",
            "- 이 사안을 특정 업체 지정 방식으로 단정하기보다 **지역제한경쟁입찰**, **종합쇼핑몰/MAS**, **중소기업자간 경쟁제품·직접생산확인**, **기술개발제품·혁신제품·우수조달물품** 여부를 함께 검토하는 방향이 안전합니다.",
            "- 구체 품목이 있으면 부산업체 후보, 조달등록, 정책기업, 인증제품 여부까지 붙여서 구매 경로를 다시 잡을 수 있습니다.",
        ])
    return None


def _clean_route_guidance_for_answer(text: str) -> str:
    """Remove prompt-only instructions from route guidance before user display."""
    cleaned = text or ""
    cleaned = cleaned.split("답변 형식 지시:")[0]
    cleaned = cleaned.replace("[구매경로 판단 재료 — 최종 답변은 아래 경로를 조합해 실무형으로 작성]", "검토할 구매 경로")
    cleaned = cleaned.replace("- 기관유형: local_government", "- 기관유형: 지방자치단체")
    cleaned = cleaned.replace("- 기관유형: central_government", "- 기관유형: 국가기관")
    cleaned = cleaned.replace("- 기관유형: public_enterprise", "- 기관유형: 공기업·준정부기관")
    cleaned = re.sub(r"^- 작성 원칙:.*(?:\n|$)", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^- 주의:.*(?:\n|$)", "", cleaned, flags=re.MULTILINE)
    return cleaned.strip()


def _route_candidate_display_options_for_answer(
    user_message: str,
    all_tool_results: list,
    generation_meta: dict | None = None,
) -> dict:
    """Derive candidate-table visibility from amount/object route cards."""
    try:
        amount = _parse_amount(user_message)
        contract_object = None
        item_name = user_message
        if generation_meta:
            contract_object = generation_meta.get("company_prefetch_contract_object")
            item_name = generation_meta.get("company_prefetch_canonical_item") or item_name
        contract_object = contract_object or _get_router_contract_object(None, user_message)
        cards = build_purchase_route_cards(
            amount=amount,
            item_name=item_name,
            contract_object=contract_object,
            tool_results=all_tool_results,
        )
        options = derive_candidate_table_display_options(cards)
        result = {
            "hidden_candidate_types": options.get("hidden_candidate_types", []),
            "preferred_order": options.get("preferred_candidate_order", []),
        }
        if generation_meta is not None:
            generation_meta["purchase_route_hidden_candidate_types"] = result["hidden_candidate_types"]
            generation_meta["purchase_route_preferred_candidate_order"] = result["preferred_order"]
            generation_meta["purchase_route_policy_company_table_hidden"] = "policy_company" in result["hidden_candidate_types"]
            generation_meta["purchase_route_card_count"] = len(cards)
        return result
    except Exception as exc:
        if generation_meta is not None:
            generation_meta["purchase_route_candidate_display_error"] = str(exc)[:300]
        return {"hidden_candidate_types": [], "preferred_order": []}


def _clean_catalog_guidance_for_answer(text: str) -> str:
    """Convert catalog guidance from prompt context into user-facing notes."""
    cleaned = text or ""
    if not cleaned.strip():
        return ""
    cleaned = cleaned.replace("[지역업체 보호·우대제도 카탈로그 매칭]", "추가로 검토할 지역업체 우대제도")
    cleaned = re.sub(r"^- 아래 제도는 질문 조건에서.*(?:\n|$)", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^- 답변에서는 사용자가 제도를.*(?:\n|$)", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("| 제도 | 선택 이유 | 답변에서 다룰 포인트 |", "| 제도 | 검토 이유 | 실무 확인 포인트 |")
    return cleaned.strip()


def _filter_company_tool_results_by_item(
    tool_results: list,
    user_message: str,
    generation_meta: dict | None = None,
) -> list:
    """Remove product-irrelevant company candidates before LLM/formatter use."""
    try:
        from policies.candidate_policy import (
            candidate_matches_user_item,
            filter_candidate_rows_by_user_item,
        )
    except Exception as exc:
        if generation_meta is not None:
            generation_meta["candidate_item_filter_error"] = str(exc)[:200]
        return tool_results

    def _filter_formatted_candidate_text(text: str) -> tuple[str, int, int]:
        lines = str(text or "").splitlines()
        if not any(re.match(r"^\d+\.\s+", line) for line in lines):
            return text, 0, 0

        prefix: list[str] = []
        blocks: list[list[str]] = []
        suffix: list[str] = []
        current: list[str] | None = None
        after_blocks = False

        for line in lines:
            if re.match(r"^\d+\.\s+", line):
                if current is not None:
                    blocks.append(current)
                current = [line]
                after_blocks = False
            elif current is not None:
                if re.match(r"^\.\.\. 외 \d+건", line.strip()):
                    blocks.append(current)
                    current = None
                    after_blocks = True
                    continue
                current.append(line)
            elif blocks or after_blocks:
                suffix.append(line)
            else:
                prefix.append(line)
        if current is not None:
            blocks.append(current)

        if not blocks:
            return text, 0, 0

        kept_blocks: list[list[str]] = []
        removed = 0
        for block in blocks:
            block_text = "\n".join(block)
            products = []
            for match in re.finditer(r"품목:\s*([^\|\n]+)", block_text):
                product = match.group(1).strip()
                if product:
                    products.append(product)
            row = {"main_products": products} if products else {}
            if products and candidate_matches_user_item(row, user_message):
                cleaned_products = []
                for product_text in products:
                    for product in re.split(r"[,，/]+", product_text):
                        product = product.strip()
                        if product and candidate_matches_user_item({"main_products": [product]}, user_message):
                            cleaned_products.append(product)
                if cleaned_products:
                    compact_seen = set()
                    unique_products = []
                    for product in cleaned_products:
                        compact = re.sub(r"\s+", "", product)
                        if compact in compact_seen:
                            continue
                        compact_seen.add(compact)
                        unique_products.append(product)
                    cleaned_block = []
                    for line in block:
                        cleaned_line = re.sub(
                            r"품목:\s*([^\|\n]+)",
                            "품목: " + ", ".join(unique_products) + " ",
                            line,
                        )
                        cleaned_block.append(cleaned_line)
                    block = cleaned_block
                kept_blocks.append(block)
            else:
                removed += 1

        if removed == 0:
            return text, 0, len(kept_blocks)

        header = "\n".join(prefix)
        kept_count = len(kept_blocks)
        header = re.sub(
            r"총\s+\d+건\s+\(상위\s+\d+건\s+표시\)",
            f"총 {kept_count}건 (품목 일치 후보 표시)",
            header,
        )
        if kept_count == 0:
            return "현재 조건에 맞는 업체 후보를 찾지 못했습니다. 품목명이나 세부 조건을 바꿔 다시 검색해 보세요.", removed, 0

        rebuilt_blocks = []
        for idx, block in enumerate(kept_blocks, start=1):
            new_block = list(block)
            new_block[0] = re.sub(r"^\d+\.", f"{idx}.", new_block[0], count=1)
            rebuilt_blocks.append("\n".join(new_block).rstrip())

        cleaned_suffix = [
            line for line in suffix
            if not re.match(r"^\.\.\. 외 \d+건", line.strip())
        ]
        parts = [header.rstrip(), "\n".join(rebuilt_blocks).rstrip(), "\n".join(cleaned_suffix).strip()]
        return "\n\n".join(part for part in parts if part), removed, kept_count

    filtered_results = []
    removed_total = 0
    kept_total = 0
    for tr in tool_results or []:
        copied = dict(tr)
        parsed = None
        result_value = copied.get("result")
        if isinstance(result_value, str) and result_value.strip().startswith("{"):
            try:
                parsed = json.loads(result_value)
            except Exception:
                parsed = None
        elif isinstance(result_value, dict):
            parsed = dict(result_value)

        if isinstance(parsed, dict) and isinstance(parsed.get("candidates"), list):
            original = [row for row in parsed.get("candidates", []) if isinstance(row, dict)]
            filtered = filter_candidate_rows_by_user_item(original, user_message)
            removed_total += max(0, len(original) - len(filtered))
            kept_total += len(filtered)
            parsed["candidates"] = filtered
            if isinstance(parsed.get("data"), list):
                parsed["data"] = filter_candidate_rows_by_user_item(parsed.get("data", []), user_message)
            copied["result"] = json.dumps(parsed, ensure_ascii=False)
        elif isinstance(result_value, str):
            filtered_text, removed, kept = _filter_formatted_candidate_text(result_value)
            if removed:
                copied["result"] = filtered_text
                removed_total += removed
                kept_total += kept

        for key in ("structured_rows", "product_sample_rows"):
            if isinstance(copied.get(key), list):
                original = [row for row in copied.get(key, []) if isinstance(row, dict)]
                filtered = filter_candidate_rows_by_user_item(original, user_message)
                removed_total += max(0, len(original) - len(filtered))
                kept_total += len(filtered)
                copied[key] = filtered

        filtered_results.append(copied)

    if generation_meta is not None:
        generation_meta["candidate_item_filter_applied"] = True
        generation_meta["candidate_item_filter_removed_count"] = removed_total
        generation_meta["candidate_item_filter_kept_count"] = kept_total
    return filtered_results


def _company_tool_label(tool_name: str) -> str:
    """Return a user-facing label for prefetched company/product result blocks."""
    name = tool_name or ""
    if "shopping_mall" in name:
        return "종합쇼핑몰/MAS 후보"
    if "certified_product" in name:
        return "기술개발제품·우수조달 등 인증제품 후보"
    if "innovation_product" in name:
        return "혁신제품·혁신시제품 후보"
    if "company_by_license" in name:
        return "부산 면허·업종 업체 후보"
    if "local_company" in name:
        return "부산 지역업체 후보"
    if "company_by_policy" in name:
        return "정책기업 후보"
    return "업체 후보"


def _build_direct_article_answer(law_query: str) -> str | None:
    """Return a compact article explanation from the internal law DB."""
    try:
        from internal_law_lookup import search_internal_law
        result = search_internal_law(law_query)
    except Exception as e:
        print(f"  [DIRECT-ARTICLE] skipped: {e}", flush=True)
        return None

    if not result:
        return None

    text = result.replace("[내부DB]", "").strip()
    if len(text) > 2400:
        text = text[:2400].rstrip() + "\n...(이하 생략)"

    return "\n".join([
        f"**{law_query}**는 내부 법령 DB에서 확인했습니다.",
        "",
        "### 원문 핵심",
        text,
        "",
        "### 실무상 읽는 법",
        "- 이 답변은 조문 자체를 확인하는 조회형 답변입니다.",
        "- 실제 계약 가능 여부는 금액, 계약유형, 기관유형, 품목·인증 여부, 행정규칙·별표 기준을 함께 봐야 합니다.",
        "",
        "⚖️ 본 답변은 내부 DB에 적재된 조문 기준의 직접 조회 결과입니다.",
    ])


def _chat_v144(

    user_message: str,
    history: list[dict],
    progress_callback=None,
    agency_type: str = None,
) -> tuple[str, list[dict]]:
    """
    v1.4.4 Dynamic Prompt Pipeline.
    3단 라우팅 → 동적 프롬프트 조립 → Function-calling loop (MAX=3)
    """
    global _current_routing_confidence_meta, _current_tool_loop_gate_meta, _current_intent_rag_meta, _current_evidence_context_meta, _current_llm_payload_meta
    request_id = str(uuid.uuid4())[:8]
    routing_start = time.time()
    _current_routing_confidence_meta = {}
    _current_tool_loop_gate_meta = {}
    _current_intent_rag_meta = {}
    _current_evidence_context_meta = {}
    _current_llm_payload_meta = {}

    global _cited_laws
    _cited_laws = []

    # ─── 0. Conservative Query Gateway ───
    # 명확한 기준카드/조문직접조회/순수 업체검색만 앞단에서 처리한다.
    # 애매하거나 사안형이면 기존 라우터+티어 흐름으로 통과시킨다.
    try:
        from router.query_gateway import decide_query_gateway
        gateway_decision = decide_query_gateway(user_message)
        print(
            f"  [QUERY-GATEWAY] route={gateway_decision.route} "
            f"confidence={gateway_decision.confidence} "
            f"reason={gateway_decision.reason} "
            f"card={gateway_decision.matched_card_id} "
            f"exclusions={gateway_decision.exclusions}",
            flush=True,
        )
    except Exception as e:
        print(f"  [QUERY-GATEWAY] skipped: {e}", flush=True)
        gateway_decision = None

    if gateway_decision and gateway_decision.route == "direct_article" and gateway_decision.law_query:
        direct_article_answer = _build_direct_article_answer(gateway_decision.law_query)
        if direct_article_answer:
            api_status = ApiStatus()
            _direct_article_meta = {
                "model_used": "internal_law_db_direct_article",
                "model_decision_reason": "query_gateway_direct_article",
                "tier_resolved": 1,
                "fast_track_applied": True,
                "deterministic_template_used": False,
                "company_table_allowed": False,
                "legal_conclusion_allowed": True,
                "candidate_table_source": "none",
                "answer_schema_version": "direct_article_lookup_v1",
                "source_status": "internal_law_db_hit",
                "rag_elapsed_ms": 0,
                "model_elapsed_ms": 0,
                "mcp_preflight_elapsed_ms": 0,
                "tool_call_count": 1,
                "company_search_status": "not_called",
                "amount_rewrite_bypass": True,
                "query_gateway_route": gateway_decision.route,
                "query_gateway_reason": gateway_decision.reason,
                "direct_legal_basis_count": 1,
            }
            answer, history = _finalize_answer(
                direct_article_answer, history, user_message, [{
                    "tool_name": "get_law_text",
                    "status": "success",
                    "result": direct_article_answer,
                    "elapsed_ms": 0,
                }], api_status, progress_callback, generation_meta=_direct_article_meta
            )
            return answer, history

    if gateway_decision and gateway_decision.route == "company_search":
        print("  [QUERY-GATEWAY] company_search fast track", flush=True)
        _current_routing_confidence_meta = {
            "routing_confidence_score": 0.85,
            "routing_confidence_level": "high",
            "routing_ambiguous": False,
            "routing_ambiguity_reasons": [],
            "routing_required_slots_missing": [],
            "routing_confidence_action": "gateway_fast_track_company_search",
        }
        api_status = ApiStatus()
        return _execute_tier_0_fast_track(
            user_message, history, api_status, progress_callback, ["company_search"]
        )

    # ─── 0.2. Intent RAG Context Resolver ───
    # Gateway가 확실히 종료하지 못한 질문만 여기서 본격적으로 의도를 보강한다.
    # Tier와 답변모드는 이 뒤의 Keyword Router/RAG/보조 Router 조합으로 결정한다.
    intent_rag_decision = _resolve_intent_rag_context(user_message)
    _current_intent_rag_meta = _intent_rag_prefixed_meta(intent_rag_decision)

    # ─── 0.5. Deterministic Legal Gate ───
    # 반복 기준/제도 설명형 질문은 LLM 의도분석보다 먼저 결정형 답변으로 처리한다.
    try:
        from policies.deterministic_legal_answer_gate import match_deterministic_legal_answer
        deterministic_legal_answer = match_deterministic_legal_answer(user_message)
    except Exception as e:
        print(f"  [DETERMINISTIC-GATE] skipped: {e}")
        deterministic_legal_answer = None

    if deterministic_legal_answer:
        api_status = ApiStatus()
        _deterministic_gate_meta = {
            "model_used": "deterministic_internal_law_db",
            "model_decision_reason": deterministic_legal_answer.reason,
            "tier_resolved": 1,
            "fast_track_applied": True,
            "deterministic_template_used": True,
            "company_table_allowed": False,
            "legal_conclusion_allowed": False,
            "candidate_table_source": "none",
            "answer_schema_version": deterministic_legal_answer.schema_version,
            "source_status": "internal_law_db_hit",
            "rag_elapsed_ms": 0,
            "model_elapsed_ms": 0,
            "mcp_preflight_elapsed_ms": 0,
            "tool_call_count": 0,
            "company_search_status": "not_called",
            "amount_rewrite_bypass": True,
            "final_answer_scanned": True,
            "forbidden_patterns_remaining_after_rewrite": [],
            "query_gateway_route": gateway_decision.route if gateway_decision else "skipped",
            "query_gateway_reason": gateway_decision.reason if gateway_decision else "",
            "query_gateway_card_id": gateway_decision.matched_card_id if gateway_decision else None,
        }
        answer, history = _finalize_answer(
            deterministic_legal_answer.answer, history, user_message, [], api_status,
            progress_callback, generation_meta=_deterministic_gate_meta
        )
        return answer, history

    # ─── 0.6. Intent RAG / PPS Q&A Interpretation Fast Gate ───
    # 조달청 질의응답·실무 해석사례형 질문은 비법령 RAG 카드로 먼저 답한다.
    try:
        pps_fast_answer, pps_fast_cards = _build_pps_qa_interpretation_fast_answer(
            user_message,
            intent_rag_decision,
        )
    except Exception as e:
        print(f"  [PPS-QA-FAST] skipped: {e}", flush=True)
        pps_fast_answer, pps_fast_cards = "", []

    if pps_fast_answer:
        api_status = ApiStatus()
        _pps_fast_meta = {
            "model_used": "intent_rag_pps_qa_fast_gate",
            "model_decision_reason": "intent_rag_pps_qa_interpretation_fast_answer",
            "tier_resolved": 1,
            "fast_track_applied": True,
            "deterministic_template_used": False,
            "company_table_allowed": False,
            "legal_conclusion_allowed": False,
            "candidate_table_source": "none",
            "answer_schema_version": "pps_qa_interpretation_fast_v1",
            "source_status": "intent_rag_pps_qa_cards",
            "rag_elapsed_ms": 0,
            "model_elapsed_ms": 0,
            "mcp_preflight_elapsed_ms": 0,
            "tool_call_count": 0,
            "company_search_status": "not_called",
            "amount_rewrite_bypass": True,
            "final_answer_scanned": True,
            "forbidden_patterns_remaining_after_rewrite": [],
            "practice_manual_card_count": 0,
            "pps_qa_card_count": len(pps_fast_cards),
            "skip_citation_verify": True,
            "final_answer_source": "intent_rag_pps_qa_fast_answer",
            "query_gateway_route": gateway_decision.route if gateway_decision else "skipped",
            "query_gateway_reason": gateway_decision.reason if gateway_decision else "",
        }
        answer, history = _finalize_answer(
            pps_fast_answer, history, user_message, [], api_status,
            progress_callback, generation_meta=_pps_fast_meta
        )
        return answer, history

    # ─── 0.7. Practice Manual Fast Gate ───
    # 개념/차이/절차/쟁점 설명형 질문은 전체 LLM 도구호출 루프 전에
    # 사전 생성된 실무 매뉴얼 카드로 답한다. 금액·법적 결론 질문은 제외한다.
    try:
        practice_fast_answer, practice_fast_cards = _build_practice_manual_fast_answer(user_message, agency_type)
    except Exception as e:
        print(f"  [PRACTICE-FAST] skipped: {e}", flush=True)
        practice_fast_answer, practice_fast_cards = "", []

    if practice_fast_answer:
        api_status = ApiStatus()
        _practice_fast_meta = {
            "model_used": "practice_manual_fast_gate",
            "model_decision_reason": "practice_manual_explanation_fast_answer",
            "tier_resolved": 1,
            "fast_track_applied": True,
            "deterministic_template_used": False,
            "company_table_allowed": False,
            "legal_conclusion_allowed": False,
            "candidate_table_source": "none",
            "answer_schema_version": "practice_manual_explanation_v1",
            "source_status": "practice_manual_cards",
            "rag_elapsed_ms": 0,
            "model_elapsed_ms": 0,
            "mcp_preflight_elapsed_ms": 0,
            "tool_call_count": 0,
            "company_search_status": "not_called",
            "amount_rewrite_bypass": True,
            "final_answer_scanned": True,
            "forbidden_patterns_remaining_after_rewrite": [],
            "practice_manual_card_count": len(practice_fast_cards),
            "pps_qa_card_count": 0,
            "skip_citation_verify": True,
            "final_answer_source": "practice_manual_fast_answer",
            "query_gateway_route": gateway_decision.route if gateway_decision else "skipped",
            "query_gateway_reason": gateway_decision.reason if gateway_decision else "",
        }
        answer, history = _finalize_answer(
            practice_fast_answer, history, user_message, [], api_status,
            progress_callback, generation_meta=_practice_fast_meta
        )
        return answer, history

    # ─── 1. Keyword Pre-Router ───
    if progress_callback:
        progress_callback("🔄 질문 분석 중...")
    keyword_result = keyword_pre_route(user_message)
    try:
        try:
            from router.intent_rag_resolver import augment_keyword_route
        except ImportError:
            from app.router.intent_rag_resolver import augment_keyword_route
        keyword_result = augment_keyword_route(keyword_result, intent_rag_decision)
    except Exception as e:
        print(f"  [INTENT-RAG] keyword merge skipped: {e}", flush=True)
    print(f"  [PRE-ROUTER] matched={keyword_result.matched_categories} "
          f"ambiguous={keyword_result.ambiguous_keywords} "
          f"unambiguous={keyword_result.is_unambiguous}")

    # ─── 2. 의도 분류 (키워드 기반, LLM 호출 없음) ───
    # Pre-Router의 키워드 매칭 결과를 직접 사용
    # LLM은 상시 1차 분류자가 아니라, 아래 3개 신호가 충돌/저신뢰일 때만 최종 검수자로 개입한다.
    legacy_router_result = None
    adjudicator_meta = {
        "enabled": USE_GEMINI_ROUTE_ADJUDICATOR,
        "called": False,
        "status": "not_required",
    }
    intent_labels = [cat for cat in keyword_result.matched_categories if cat != "unclear"]
    if not intent_labels:
        intent_labels = ["common_procurement"]
    if _is_legal_definition_query(user_message):
        intent_labels = [
            label for label in intent_labels
            if label not in ("company_search", "company_detail", "policy_candidate_search")
        ]
        if "common_procurement" not in intent_labels:
            intent_labels.append("common_procurement")

    # Intent RAG는 LLM Router와 독립된 보조 판정이다. 신뢰도가 충분할 때만
    # label을 보강하고, 업체 목록 요청이 아닌 지역구매지원 질문은 company_search를 제거한다.
    if intent_rag_decision is not None and getattr(intent_rag_decision, "confidence", 0.0) >= 0.55:
        if getattr(intent_rag_decision, "company_search_blocked", False):
            intent_labels = [label for label in intent_labels if label != "company_search"]
        for label in getattr(intent_rag_decision, "intent_labels", []) or []:
            if label == "company_search" and not getattr(intent_rag_decision, "company_search_required", False):
                continue
            if label not in intent_labels:
                intent_labels.append(label)

    # ─── 2.5. Conditional LLM Route Adjudicator ───
    # 정규화 엔진 + Keyword Router + Intent RAG 결과가 명확하면 LLM을 부르지 않는다.
    # 충돌/저신뢰/슬롯 누락/복합 신호가 있을 때만 카드 기반 최종 라우팅 검수자로 사용한다.
    try:
        try:
            from router.llm_route_adjudicator import (
                build_llm_adjudication_card,
                evaluate_llm_adjudication_need,
            )
        except ImportError:
            from app.router.llm_route_adjudicator import (
                build_llm_adjudication_card,
                evaluate_llm_adjudication_need,
            )
        adjudication_need = evaluate_llm_adjudication_need(
            user_message,
            gateway_decision=gateway_decision,
            keyword_result=keyword_result,
            intent_rag_decision=intent_rag_decision,
            intent_labels=intent_labels,
        )
        adjudicator_meta.update({
            "required": adjudication_need.required,
            "reasons": list(adjudication_need.reasons),
            "conflicts": list(adjudication_need.conflicts),
            "missing_slots": list(adjudication_need.missing_slots),
            "complex_signal_count": adjudication_need.complex_signal_count,
            "rag_confidence": adjudication_need.rag_confidence,
            "keyword_unambiguous": adjudication_need.keyword_unambiguous,
            "bypass_reason": adjudication_need.bypass_reason,
        })
        if adjudication_need.required and USE_GEMINI_ROUTE_ADJUDICATOR:
            adjudication_card = build_llm_adjudication_card(
                user_message,
                gateway_decision=gateway_decision,
                keyword_result=keyword_result,
                intent_rag_decision=intent_rag_decision,
                intent_labels=intent_labels,
                need=adjudication_need,
            )
            legacy_router_result, call_meta = _run_llm_route_adjudicator(user_message, adjudication_card)
            adjudicator_meta.update(call_meta)
            if legacy_router_result is not None:
                intent_labels, label_meta = _apply_router_adjudication_to_labels(
                    intent_labels,
                    legacy_router_result,
                    user_message,
                )
                adjudicator_meta.update(label_meta)
        else:
            print(
                f"  [LLM-ADJUDICATOR] skipped: {adjudication_need.bypass_reason or 'not_required'}",
                flush=True,
            )
    except Exception as e:
        print(f"  [LLM-ADJUDICATOR] evaluation skipped: {e}", flush=True)
        adjudicator_meta.update({
            "status": "evaluation_failed",
            "error": str(e)[:300],
        })

    legacy_router_meta = _router_result_to_meta(legacy_router_result)
    legacy_router_meta["mode"] = "conditional_route_adjudicator"
    legacy_router_meta["enabled"] = USE_GEMINI_ROUTE_ADJUDICATOR
    legacy_router_meta["adjudicator"] = dict(adjudicator_meta)

    # ─── 2.7. Intent Frame → Route Plan ───
    # 여기서부터는 질문을 다시 분류하지 않는다. 앞단 신호를 하나의
    # IntentFrame으로 확정하고, RoutePlan은 그 결과를 실행계획으로만 번역한다.
    intent_frame = None
    route_plan = None
    try:
        try:
            from router.route_resolver import build_intent_frame, resolve_route_plan
        except ImportError:
            from app.router.route_resolver import build_intent_frame, resolve_route_plan
        intent_frame = build_intent_frame(
            user_message,
            gateway_decision=gateway_decision,
            keyword_result=keyword_result,
            intent_rag_decision=intent_rag_decision,
            router_result=legacy_router_result,
            intent_labels=intent_labels,
        )
        route_plan = resolve_route_plan(intent_frame)
        intent_labels = list(intent_frame.labels)
        legacy_router_meta["intent_frame"] = intent_frame.to_meta()
        legacy_router_meta["route_plan"] = route_plan.to_meta()
        legacy_router_meta["route_plan_mode"] = "intent_frame_resolver"
        print(
            f"  [ROUTE-RESOLVER] mode={route_plan.execution_mode} "
            f"legacy_tier={route_plan.query_tier} "
            f"sections={list(route_plan.answer_sections)} "
            f"retrieval={list(route_plan.retrieval_needs)}",
            flush=True,
        )
    except Exception as e:
        print(f"  [ROUTE-RESOLVER] skipped: {e}", flush=True)
        legacy_router_meta["route_plan_mode"] = "fallback_legacy_tier"
        legacy_router_meta["route_plan_error"] = str(e)[:300]
    
    # IntentRouteResult 호환 객체 생성 (guardrail_selector 호환용)
    from prompting.schemas import IntentRouteResult, IntentCandidate
    intent_result = IntentRouteResult(
        candidates=[IntentCandidate(label=lbl, confidence=0.90) for lbl in intent_labels],
        agency_type="local_government",
        needs_clarification=None,
        mcp_required=True,
        router_status="llm_adjudicated" if legacy_router_result is not None else "keyword_rag_only",
    )
    print(f"  [INTENT] labels={intent_labels} ({intent_result.router_status})")

    # ─── 3. Guardrail 선택 + Sanity Check ───
    initial_guardrails = select_guardrails(intent_result, keyword_result)
    guardrails = apply_guardrail_sanity_check(user_message, initial_guardrails)
    sanity_added = list(set(guardrails) - set(initial_guardrails))
    print(f"  [GUARDRAILS] {guardrails} (Sanity added: {sanity_added})")

    # ─── 4. Risk + Legacy Tier 호환값 ───
    # 실제 실행 판단은 RoutePlan의 execution_mode/retrieval_needs/company_search_mode가 담당한다.
    # query_tier는 기존 로그·후처리·레거시 함수 호환용 숫자로만 유지한다.
    from policies.model_routing_policy import classify_risk
    risk_info = classify_risk(user_message, intent_labels)
    if route_plan is not None:
        query_tier = route_plan.query_tier
    else:
        from policies.model_routing_policy import classify_query_tier
        query_tier = classify_query_tier(risk_info, intent_labels, user_message, legacy_router_result)
    try:
        try:
            from app.router.routing_confidence import assess_routing_confidence
        except ImportError:
            from router.routing_confidence import assess_routing_confidence
        routing_confidence = assess_routing_confidence(
            user_message,
            gateway_decision=gateway_decision,
            keyword_result=keyword_result,
            router_result=legacy_router_result,
            intent_labels=intent_labels,
            query_tier=query_tier,
            intent_rag_result=intent_rag_decision,
        )
        _current_routing_confidence_meta = {
            "routing_confidence_score": routing_confidence.score,
            "routing_confidence_level": routing_confidence.level,
            "routing_ambiguous": routing_confidence.ambiguous,
            "routing_ambiguity_reasons": routing_confidence.reasons,
            "routing_required_slots_missing": routing_confidence.required_slots_missing,
            "routing_confidence_action": routing_confidence.action,
        }
        if routing_confidence.tier_override is not None and routing_confidence.tier_override != query_tier:
            print(
                f"  [ROUTING-CONFIDENCE] tier override {query_tier} -> {routing_confidence.tier_override} "
                f"because {routing_confidence.reasons}",
                flush=True,
            )
            query_tier = routing_confidence.tier_override
            _current_routing_confidence_meta["routing_tier_overridden"] = True
            _current_routing_confidence_meta["routing_tier_override_to"] = query_tier
    except Exception as e:
        print(f"  [ROUTING-CONFIDENCE] skipped: {e}", flush=True)
        _current_routing_confidence_meta = {
            "routing_confidence_score": 0.5,
            "routing_confidence_level": "unknown",
            "routing_ambiguous": True,
            "routing_ambiguity_reasons": [f"confidence_assessment_failed:{e}"],
            "routing_required_slots_missing": [],
            "routing_confidence_action": "proceed",
        }
    legacy_router_meta["routing_confidence"] = dict(_current_routing_confidence_meta)
    legal_preflight_required = _should_run_legal_preflight_from_route_plan(
        route_plan if 'route_plan' in locals() else None,
        query_tier,
    )
    fast_track_required = _should_fast_track_from_route_plan(
        route_plan if 'route_plan' in locals() else None,
        _current_routing_confidence_meta,
        query_tier,
    )
    print(
        f"  [ROUTING] risk_level={risk_info.get('risk_level')} "
        f"execution_mode={_route_plan_execution_mode(route_plan) if 'route_plan' in locals() else ''} "
        f"legacy_tier={query_tier} "
        f"legal_preflight={legal_preflight_required} "
        f"confidence={_current_routing_confidence_meta.get('routing_confidence_level')} "
        f"score={_current_routing_confidence_meta.get('routing_confidence_score')}",
        flush=True,
    )
    
    if fast_track_required:
        print("  [FAST-TRACK] RoutePlan company_fast_track detected. Bypassing Gemini completely.")
        api_status = ApiStatus()
        return _execute_tier_0_fast_track(user_message, history, api_status, progress_callback, intent_labels)
        
    amount_detected = _parse_amount(user_message)
    # ━━━ 법령 RAG 완전 제거 ━━━
    # 법령은 MCP preflight(내부 DB → 외부 MCP)가 전담
    # RAG는 실무 가이드(Q&A/매뉴얼/혁신/기술) 전용
    skip_law_rag = True  # 항상 스킵
    
    # RAG elapsed time must be initialized
    rag_elapsed_ms = 0

    # ─── 5. MCP Preflight (법령 내부DB 조회 — 핵심 데이터, 먼저 실행) ───
    mandatory_mcp_plan = []
    mandatory_mcp_executed = []
    mandatory_mcp_missing = []
    evidence_cards = []
    mcp_preflight_elapsed_ms = 0
    cache_stats = {}
    
    if legal_preflight_required:
        from policies.model_routing_policy import generate_mandatory_mcp_plan
        agency_key_for_mcp = _normalize_agency_type(agency_type) if agency_type else "default"
        mandatory_mcp_plan = generate_mandatory_mcp_plan(
            user_message,
            query_tier,
            agency_type=agency_key_for_mcp,
            route_plan=route_plan if 'route_plan' in locals() else None,
        )
        if mandatory_mcp_plan:
            print(
                f"  [MCP-PREFLIGHT] Starting: mode={_route_plan_execution_mode(route_plan) if 'route_plan' in locals() else 'legacy'} "
                f"legacy_tier={query_tier}, agency={agency_key_for_mcp}, plan={len(mandatory_mcp_plan)} items",
                flush=True,
            )
            preflight_start = time.time()
            mcp_context, _, mandatory_mcp_executed, mandatory_mcp_missing, cache_stats = _execute_tier_2_mandatory_mcp(
                user_message, mandatory_mcp_plan, progress_callback
            )
            mcp_preflight_elapsed_ms = int((time.time() - preflight_start) * 1000)
            evidence_cards = cache_stats.get("evidence_cards", [])
            _current_evidence_context_meta = {
                key: value
                for key, value in cache_stats.items()
                if key.startswith("mcp_context_") or key.startswith("evidence_context_")
            }
            print(f"  [MCP-PREFLIGHT] Done: executed={len(mandatory_mcp_executed)}, missing={len(mandatory_mcp_missing)}, elapsed={mcp_preflight_elapsed_ms}ms", flush=True)

    # ─── 6. RAG 완전 제거 — 법령은 MCP, 매뉴얼은 Phase 2에서 법령DB로 통합 예정 ───
    rag_context = ""
    rag_elapsed_ms = 0

    # MCP 법령 결과를 컨텍스트로 주입
    if legal_preflight_required and mandatory_mcp_plan and 'mcp_context' in locals():
        rag_context = f"### [법령 근거 — 최신 법령 기반, 법적 판단 우선]\n{mcp_context}"

    # ─── 6.5. Practice Manual Cards (precomputed, no PDF/runtime embedding) ───
    practice_manual_cards = []
    practice_manual_context = ""
    practice_contract_object = _get_router_contract_object(
        legacy_router_result if 'legacy_router_result' in locals() else None,
        user_message,
    )
    try:
        practice_manual_cards = match_practice_manual_cards(
            user_message,
            contract_object=practice_contract_object,
            agency_type=agency_key_for_mcp if 'agency_key_for_mcp' in locals() else (_normalize_agency_type(agency_type) if agency_type else "default"),
            max_cards=5,
        )
        practice_manual_context = format_practice_manual_cards_for_llm(practice_manual_cards)
        if practice_manual_context:
            rag_context = (rag_context + "\n\n" if rag_context else "") + practice_manual_context
            print(f"  [PRACTICE-CARDS] matched={len(practice_manual_cards)} object={practice_contract_object}", flush=True)
    except Exception as e:
        print(f"  [PRACTICE-CARDS] skipped: {e}", flush=True)
        practice_manual_cards = []
        practice_manual_context = ""

    # ─── 6.6. PPS Q&A Interpretation Cards ───
    # 조달청 질의응답은 실무 해석 보조자료로만 사용한다.
    # 금액·조문·시행일·최종 법적 결론은 내부 법령 DB/source_map이 우선한다.
    pps_qa_cards = []
    pps_qa_context = ""
    try:
        pps_qa_cards = match_pps_qa_cards(user_message, max_cards=3)
        pps_qa_context = format_pps_qa_cards_for_llm(pps_qa_cards)
        if pps_qa_context:
            rag_context = (rag_context + "\n\n" if rag_context else "") + pps_qa_context
            print(f"  [PPS-QA-CARDS] matched={len(pps_qa_cards)}", flush=True)
    except Exception as e:
        print(f"  [PPS-QA-CARDS] skipped: {e}", flush=True)
        pps_qa_cards = []
        pps_qa_context = ""

    # ─── 6.7. Tool Loop Gate (shadow by default) ───
    # LLM 도구 루프는 기본적으로 비활성화한다. 이 gate는 사전수집 근거가
    # writer-only에 충분한지 관찰/기록하고, 필요 시 운영자가 재활성화할 때
    # 제한 조건으로 사용한다.
    try:
        tool_loop_gate_decision = assess_tool_loop_gate(
            user_message=user_message,
            query_tier=query_tier,
            mandatory_mcp_plan=mandatory_mcp_plan,
            mandatory_mcp_executed=mandatory_mcp_executed,
            mandatory_mcp_missing=mandatory_mcp_missing,
            evidence_cards=evidence_cards,
            practice_manual_cards=practice_manual_cards,
            pps_qa_cards=pps_qa_cards,
            routing_confidence=_current_routing_confidence_meta,
            gateway_route=gateway_decision.route if gateway_decision else None,
            has_amount=amount_detected is not None,
            route_plan=route_plan if 'route_plan' in locals() else None,
        )
        _current_tool_loop_gate_meta = tool_loop_gate_decision.to_meta()
        print(
            "  [TOOL-LOOP-GATE] "
            f"mode={tool_loop_gate_decision.mode} "
            f"recommendation={tool_loop_gate_decision.recommendation} "
            f"score={tool_loop_gate_decision.evidence_sufficiency_score} "
            f"blockers={tool_loop_gate_decision.blockers}",
            flush=True,
        )
    except Exception as e:
        _current_tool_loop_gate_meta = {
            "tool_loop_gate_mode": os.getenv("TOOL_LOOP_GATE_MODE", "shadow").lower(),
            "tool_loop_gate_recommendation": "gate_failed_open",
            "tool_loop_gate_evidence_sufficiency_score": 0.0,
            "tool_loop_gate_should_allow_loop": True,
            "tool_loop_gate_can_use_writer_only": False,
            "tool_loop_gate_reasons": [f"gate_failed:{e}"],
            "tool_loop_gate_blockers": ["gate_failed"],
        }
        print(f"  [TOOL-LOOP-GATE] failed-open: {e}", flush=True)

    # ─── 5.5. Grounded Single-Pass LLM ───
    # 실제 금액/품목 판단 질문은 결정형 템플릿으로 덮지 않고,
    # 내부 DB preflight 근거만 넣어 LLM이 1회 문장화한다.
    if (
        'mcp_context' in locals()
        and mandatory_mcp_executed
        and _should_use_grounded_single_pass_llm(
            user_message,
            query_tier,
            amount_detected,
            route_plan if 'route_plan' in locals() else None,
        )
    ):
        grounded_start = time.time()
        grounded_context = mcp_context
        if practice_manual_context:
            grounded_context = f"{mcp_context}\n\n{practice_manual_context}"
        if pps_qa_context:
            grounded_context = f"{grounded_context}\n\n{pps_qa_context}"
        simple_amount_answer = _build_simple_amount_contract_answer(user_message, amount_detected)
        if simple_amount_answer:
            pps_qa_answer_section = render_pps_qa_cards_for_answer(pps_qa_cards)
            if pps_qa_answer_section:
                simple_amount_answer = f"{simple_amount_answer}\n\n{pps_qa_answer_section}"
            grounded_tool_results = [{
                "tool_name": "chain_full_research",
                "status": "success",
                "result": mcp_context,
                "elapsed_ms": mcp_preflight_elapsed_ms,
            }]
            api_status = ApiStatus()
            _simple_amount_meta = {
                "model_used": "deterministic_internal_law_db",
                "model_decision_reason": "simple_amount_contract_fast_answer",
                "tier_resolved": query_tier,
                "fast_track_applied": False,
                "deterministic_template_used": True,
                "amount_rewrite_bypass": True,
                "company_table_allowed": False,
                "legal_conclusion_allowed": True,
                "candidate_table_source": "none",
                "answer_schema_version": "simple_amount_contract_v1",
                "source_status": "mcp_preflight_success",
                "rag_elapsed_ms": 0,
                "model_elapsed_ms": int((time.time() - grounded_start) * 1000),
                "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
                "tool_call_count": len(grounded_tool_results),
                "direct_legal_basis_count": len(mandatory_mcp_executed),
                "mandatory_mcp_plan": mandatory_mcp_plan,
                "mandatory_mcp_executed": mandatory_mcp_executed,
                "mandatory_mcp_missing": mandatory_mcp_missing,
                "evidence_cards": evidence_cards,
                "evidence_card_count": cache_stats.get("evidence_card_count", 0),
                "internal_db_hit_count": cache_stats.get("internal_db_hit_count", 0),
                "external_mcp_fallback_count": cache_stats.get("external_mcp_fallback_count", 0),
                "evidence_missing_count": cache_stats.get("evidence_missing_count", 0),
                "company_search_status": "not_called",
                "grounded_single_pass_llm": False,
                "practice_manual_card_count": len(practice_manual_cards),
                "pps_qa_card_count": len(pps_qa_cards),
                "skip_citation_verify": True,
            }
            answer, history = _finalize_answer(
                simple_amount_answer, history, user_message, grounded_tool_results, api_status,
                progress_callback, generation_meta=_simple_amount_meta
            )
            return answer, history

        direct_grounded_answer = _build_grounded_case_timeout_fallback(user_message, grounded_context)
        if direct_grounded_answer and "바로 단정하기 어렵습니다" not in direct_grounded_answer:
            pps_qa_answer_section = render_pps_qa_cards_for_answer(pps_qa_cards)
            if pps_qa_answer_section:
                direct_grounded_answer = f"{direct_grounded_answer}\n\n{pps_qa_answer_section}"
            grounded_tool_results = [{
                "tool_name": "chain_full_research",
                "status": "success",
                "result": mcp_context,
                "elapsed_ms": mcp_preflight_elapsed_ms,
            }]
            api_status = ApiStatus()
            _direct_grounded_meta = {
                "model_used": "deterministic_internal_law_db",
                "model_decision_reason": "clear_grounded_industry_law_fast_answer",
                "tier_resolved": query_tier,
                "fast_track_applied": False,
                "deterministic_template_used": True,
                "amount_rewrite_bypass": True,
                "company_table_allowed": False,
                "legal_conclusion_allowed": True,
                "candidate_table_source": "none",
                "answer_schema_version": "clear_grounded_industry_law_v1",
                "source_status": "mcp_preflight_success",
                "rag_elapsed_ms": 0,
                "model_elapsed_ms": 0,
                "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
                "tool_call_count": len(grounded_tool_results),
                "direct_legal_basis_count": len(mandatory_mcp_executed),
                "mandatory_mcp_plan": mandatory_mcp_plan,
                "mandatory_mcp_executed": mandatory_mcp_executed,
                "mandatory_mcp_missing": mandatory_mcp_missing,
                "evidence_cards": evidence_cards,
                "evidence_card_count": cache_stats.get("evidence_card_count", 0),
                "internal_db_hit_count": cache_stats.get("internal_db_hit_count", 0),
                "external_mcp_fallback_count": cache_stats.get("external_mcp_fallback_count", 0),
                "evidence_missing_count": cache_stats.get("evidence_missing_count", 0),
                "company_search_status": "not_called",
                "grounded_single_pass_llm": False,
                "practice_manual_card_count": len(practice_manual_cards),
                "pps_qa_card_count": len(pps_qa_cards),
                "skip_citation_verify": True,
            }
            answer, history = _finalize_answer(
                direct_grounded_answer, history, user_message, grounded_tool_results, api_status,
                progress_callback, generation_meta=_direct_grounded_meta
            )
            return answer, history

        grounded_answer = _generate_grounded_single_pass_answer(
            user_message=user_message,
            mcp_context=grounded_context,
            agency_type=agency_type,
        )
        grounded_tool_results = [{
            "tool_name": "chain_full_research",
            "status": "success",
            "result": mcp_context,
            "elapsed_ms": mcp_preflight_elapsed_ms,
        }]
        if grounded_answer:
            api_status = ApiStatus()
            _grounded_meta = {
                "model_used": MODEL_ID,
                "model_decision_reason": "grounded_single_pass_llm_with_internal_law_db",
                "tier_resolved": query_tier,
                "fast_track_applied": False,
                "deterministic_template_used": False,
                "amount_rewrite_bypass": True,
                "company_table_allowed": False,
                "legal_conclusion_allowed": True,
                "candidate_table_source": "none",
                "answer_schema_version": "grounded_case_guidance_v1",
                "source_status": "mcp_preflight_success",
                "rag_elapsed_ms": 0,
                "model_elapsed_ms": int((time.time() - grounded_start) * 1000),
                "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
                "tool_call_count": len(grounded_tool_results),
                "direct_legal_basis_count": len(mandatory_mcp_executed),
                "mandatory_mcp_plan": mandatory_mcp_plan,
                "mandatory_mcp_executed": mandatory_mcp_executed,
                "mandatory_mcp_missing": mandatory_mcp_missing,
                "evidence_cards": evidence_cards,
                "evidence_card_count": cache_stats.get("evidence_card_count", 0),
                "internal_db_hit_count": cache_stats.get("internal_db_hit_count", 0),
                "external_mcp_fallback_count": cache_stats.get("external_mcp_fallback_count", 0),
                "evidence_missing_count": cache_stats.get("evidence_missing_count", 0),
                "legal_basis_cache_used": cache_stats.get("legal_basis_cache_used", False),
                "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0),
                "legal_basis_cache_miss_count": cache_stats.get("legal_basis_cache_miss_count", 0),
                "mcp_called_for_cache_miss": cache_stats.get("mcp_called_for_cache_miss", False),
                "mcp_called_for_freshness": cache_stats.get("mcp_called_for_freshness", False),
                "company_search_status": "not_called",
                "grounded_single_pass_llm": True,
                "practice_manual_card_count": len(practice_manual_cards),
                "pps_qa_card_count": len(pps_qa_cards),
                "skip_citation_verify": True,
            }
            answer, history = _finalize_answer(
                grounded_answer, history, user_message, grounded_tool_results, api_status,
                progress_callback, generation_meta=_grounded_meta
            )
            return answer, history

        api_status = ApiStatus()
        _grounded_fallback_meta = {
            "model_used": "grounded_case_timeout_fallback",
            "model_decision_reason": "internal_law_db_read_llm_timeout",
            "tier_resolved": query_tier,
            "fast_track_applied": False,
            "deterministic_template_used": False,
            "amount_rewrite_bypass": True,
            "company_table_allowed": False,
            "legal_conclusion_allowed": True,
            "candidate_table_source": "none",
            "answer_schema_version": "grounded_case_timeout_fallback_v1",
            "source_status": "mcp_preflight_success",
            "rag_elapsed_ms": 0,
            "model_elapsed_ms": int((time.time() - grounded_start) * 1000),
            "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
            "tool_call_count": len(grounded_tool_results),
            "direct_legal_basis_count": len(mandatory_mcp_executed),
            "mandatory_mcp_plan": mandatory_mcp_plan,
            "mandatory_mcp_executed": mandatory_mcp_executed,
            "mandatory_mcp_missing": mandatory_mcp_missing,
            "evidence_cards": evidence_cards,
            "evidence_card_count": cache_stats.get("evidence_card_count", 0),
            "internal_db_hit_count": cache_stats.get("internal_db_hit_count", 0),
            "external_mcp_fallback_count": cache_stats.get("external_mcp_fallback_count", 0),
            "evidence_missing_count": cache_stats.get("evidence_missing_count", 0),
            "legal_basis_cache_used": cache_stats.get("legal_basis_cache_used", False),
            "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0),
            "legal_basis_cache_miss_count": cache_stats.get("legal_basis_cache_miss_count", 0),
            "mcp_called_for_cache_miss": cache_stats.get("mcp_called_for_cache_miss", False),
            "mcp_called_for_freshness": cache_stats.get("mcp_called_for_freshness", False),
            "company_search_status": "not_called",
            "grounded_single_pass_llm": False,
            "grounded_llm_timeout": True,
            "practice_manual_card_count": len(practice_manual_cards),
            "pps_qa_card_count": len(pps_qa_cards),
            "skip_citation_verify": True,
            "fallback_used": False,
            "fallback_reason": "",
        }
        grounded_fallback_answer = _build_grounded_case_timeout_fallback(user_message, grounded_context)
        pps_qa_answer_section = render_pps_qa_cards_for_answer(pps_qa_cards)
        if pps_qa_answer_section:
            grounded_fallback_answer = f"{grounded_fallback_answer}\n\n{pps_qa_answer_section}"
        answer, history = _finalize_answer(
            grounded_fallback_answer,
            history,
            user_message,
            grounded_tool_results,
            api_status,
            progress_callback,
            generation_meta=_grounded_fallback_meta,
        )
        return answer, history

    # [FAIL_TO_CACHE] MCP preflight 전부 실패 시 LLM 루프 우회 → deterministic template
    _ftc_flag = os.getenv("MCP_FAIL_TO_CACHE", "false").lower() == "true"
    if _ftc_flag and mandatory_mcp_missing and not mandatory_mcp_executed:
        print("  [FAIL_TO_CACHE] All MCP preflight failed. Bypassing LLM loop → deterministic template.")
        api_status = ApiStatus()
        _ftc_meta = {
            "model_used": "bypass_timeout_fallback",
            "tier_resolved": query_tier,
            "mandatory_mcp_plan": [{"name": p["name"], "args": p["args"]} for p in mandatory_mcp_plan] if mandatory_mcp_plan else [],
            "mandatory_mcp_executed": mandatory_mcp_executed,
            "mandatory_mcp_missing": mandatory_mcp_missing,
            "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
            "rag_elapsed_ms": rag_elapsed_ms,
            "model_elapsed_ms": 0,
            "tool_call_count": 0,
            "legal_basis_cache_used": True,
            "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0) if cache_stats else 0,
            "legal_basis_cache_miss_count": cache_stats.get("legal_basis_cache_miss_count", 0) if cache_stats else 0,
            "source_status": "mcp_failed_no_basis",
            "deterministic_template_used": True,
            "fast_track_applied": True,
            "company_table_allowed": False,
            "core_prompt_hash": __import__('hashlib').sha256(b"ftc_bypass_core").hexdigest(),
            "prompt_prefix_hash": __import__('hashlib').sha256(b"ftc_bypass_prefix").hexdigest()[:16],
        }
        _ftc_answer = (
            "---\n⚠️ **확인 필요 사항**\n"
            "- API 지연으로 일부 판단이 제한되었습니다.\n\n"
            "[확인 필요] 법령 조회 지연으로 법적 결론을 확정할 수 없습니다.\n"
            "관련 법령 및 기관 내부 기준을 직접 확인하시기 바랍니다."
        )
        answer, history = _finalize_answer(_ftc_answer, history, user_message, [], api_status, progress_callback, generation_meta=_ftc_meta)
        return answer, history

    api_status = ApiStatus()
    try:
        from policies.deterministic_legal_answer_gate import match_deterministic_legal_answer
        deterministic_legal_answer = match_deterministic_legal_answer(user_message)
    except Exception as e:
        print(f"  [DETERMINISTIC-GATE] skipped: {e}")
        deterministic_legal_answer = None

    if deterministic_legal_answer:
        _deterministic_gate_meta = {
            "model_used": "deterministic_internal_law_db",
            "model_decision_reason": deterministic_legal_answer.reason,
            "tier_resolved": 1,
            "fast_track_applied": True,
            "deterministic_template_used": True,
            "company_table_allowed": False,
            "legal_conclusion_allowed": False,
            "candidate_table_source": "none",
            "answer_schema_version": deterministic_legal_answer.schema_version,
            "source_status": "internal_law_db_hit",
            "rag_elapsed_ms": 0,
            "model_elapsed_ms": 0,
            "mcp_preflight_elapsed_ms": 0,
            "tool_call_count": 0,
            "company_search_status": "not_called",
            "amount_rewrite_bypass": True,
            "final_answer_scanned": True,
            "forbidden_patterns_remaining_after_rewrite": [],
        }
        answer, history = _finalize_answer(
            deterministic_legal_answer.answer, history, user_message, [], api_status,
            progress_callback, generation_meta=_deterministic_gate_meta
        )
        return answer, history

    regional_restriction_fast_answer = _try_regional_restriction_standard_fast_answer(user_message)
    if regional_restriction_fast_answer:
        _regional_restriction_meta = {
            "model_used": "deterministic_internal_law_db",
            "model_decision_reason": "regional_restriction_standard_fast_answer",
            "tier_resolved": 1,
            "fast_track_applied": True,
            "deterministic_template_used": True,
            "company_table_allowed": False,
            "legal_conclusion_allowed": False,
            "candidate_table_source": "none",
            "answer_schema_version": "regional_restriction_standard_v1",
            "source_status": "internal_law_db_hit",
            "rag_elapsed_ms": 0,
            "model_elapsed_ms": 0,
            "mcp_preflight_elapsed_ms": 0,
            "tool_call_count": 0,
            "company_search_status": "not_called",
            "amount_rewrite_bypass": True,
            "final_answer_scanned": True,
            "forbidden_patterns_remaining_after_rewrite": [],
        }
        answer, history = _finalize_answer(
            regional_restriction_fast_answer, history, user_message, [], api_status,
            progress_callback, generation_meta=_regional_restriction_meta
        )
        return answer, history

    definition_fast_answer = _try_legal_definition_fast_answer(user_message)
    if definition_fast_answer:
        _definition_meta = {
            "model_used": "deterministic_internal_law_db",
            "model_decision_reason": "legal_definition_fast_answer",
            "tier_resolved": query_tier,
            "fast_track_applied": True,
            "deterministic_template_used": True,
            "company_table_allowed": False,
            "legal_conclusion_allowed": False,
            "candidate_table_source": "none",
            "answer_schema_version": "legal_definition_v1",
            "source_status": "internal_admin_rule_hit",
            "rag_elapsed_ms": 0,
            "model_elapsed_ms": 0,
            "mcp_preflight_elapsed_ms": 0,
            "tool_call_count": 1,
            "company_search_status": "not_called",
            "final_answer_scanned": True,
            "forbidden_patterns_remaining_after_rewrite": [],
        }
        answer, history = _finalize_answer(
            definition_fast_answer, history, user_message, [], api_status,
            progress_callback, generation_meta=_definition_meta
        )
        return answer, history
    agency_key = _normalize_agency_type(agency_type) if agency_type else "default"

    assembled = assemble_prompt(
        keyword_result=keyword_result,
        intent_result=intent_result,
        guardrails=guardrails,
        user_question=user_message,
        rag_context=rag_context,
        api_status=api_status,
        agency_type=agency_key,
    )
    router_guidance_context = _build_router_guidance_context(
        legacy_router_result if 'legacy_router_result' in locals() else None
    )
    intent_rag_guidance_context = _build_intent_rag_guidance_context(
        intent_rag_decision if 'intent_rag_decision' in locals() else None
    )
    route_plan_guidance_context = ""
    if 'intent_frame' in locals() and intent_frame is not None and 'route_plan' in locals() and route_plan is not None:
        try:
            try:
                from router.route_resolver import format_route_plan_for_llm
            except ImportError:
                from app.router.route_resolver import format_route_plan_for_llm
            route_plan_guidance_context = format_route_plan_for_llm(intent_frame, route_plan)
        except Exception as e:
            print(f"  [ROUTE-RESOLVER] guidance skipped: {e}", flush=True)
    dynamic_context = assembled.dynamic_context
    if intent_rag_guidance_context:
        dynamic_context = intent_rag_guidance_context + "\n\n" + dynamic_context
    if route_plan_guidance_context:
        dynamic_context = route_plan_guidance_context + "\n\n" + dynamic_context
    if router_guidance_context and not route_plan_guidance_context:
        dynamic_context = router_guidance_context + "\n\n" + dynamic_context

    _current_llm_payload_meta = {
        "llm_payload_core_prompt_chars": _text_char_len(assembled.core_prompt),
        "llm_payload_dynamic_context_chars": _text_char_len(dynamic_context),
        "llm_payload_rag_context_chars": _text_char_len(rag_context),
        "llm_payload_mcp_context_chars": _text_char_len(mcp_context if 'mcp_context' in locals() else ""),
        "llm_payload_practice_context_chars": _text_char_len(practice_manual_context if 'practice_manual_context' in locals() else ""),
        "llm_payload_pps_qa_context_chars": _text_char_len(pps_qa_context if 'pps_qa_context' in locals() else ""),
        "llm_payload_route_plan_guidance_chars": _text_char_len(route_plan_guidance_context),
        "llm_payload_intent_rag_guidance_chars": _text_char_len(intent_rag_guidance_context),
        "llm_payload_router_guidance_chars": _text_char_len(router_guidance_context),
        "llm_payload_tool_count_available": len(filtered_funcs) if 'filtered_funcs' in locals() else 0,
        "llm_payload_model_round_count": 0,
        "llm_payload_model_timeout_count": 0,
        "llm_payload_model_error_statuses": [],
    }

    routing_elapsed = int((time.time() - routing_start) * 1000)

    # 라우팅 로그 (P0-8: prompt_prefix_hash 포함)
    log_routing(
        request_id=request_id,
        question=user_message,
        keyword_result={
            "matched": keyword_result.matched_categories,
            "ambiguous": keyword_result.ambiguous_keywords,
        },
        intent_result={
            "candidates": [{"label": c.label, "confidence": c.confidence}
                           for c in intent_result.candidates],
            "status": intent_result.router_status,
        },
        selected_guardrails=guardrails,
        sanity_added_guardrails=sanity_added,
        core_prompt_hash=assembled.core_prompt_hash,
        prompt_prefix_hash=assembled.prompt_prefix_hash,
        elapsed_ms=routing_elapsed,
    )

    # ─── 6. Gemini 설정 (Core = system_instruction, Dynamic = user content) ───
    # 1) 업체검색 도구 필터링 (User Rule 1) 및 초저지연 최적화    
    company_tools = ["search_local_company_by_product", "search_local_company_by_license", "search_local_company_by_category"]
    shopping_tools = ["search_shopping_mall"]
    policy_company_tools = ["search_company_by_policy"]
    product_tools = ["search_certified_product", "search_innovation_product", "search_innovation_products", 
                      "search_tech_development_products", "search_excellent_procurement_product"]
    tool_loop_gate_mode = _current_tool_loop_gate_meta.get("tool_loop_gate_mode", "shadow")
    tool_loop_gate_writer_only_enforced = (
        tool_loop_gate_mode in ("enforce", "writer_only", "writer_only_enforce")
        and _current_tool_loop_gate_meta.get("tool_loop_gate_recommendation") == "writer_only_candidate"
        and _current_tool_loop_gate_meta.get("tool_loop_gate_can_use_writer_only") is True
    )
    
    # low-risk company_search일 경우 법령 도구 스킵하여 지연 최소화
    skip_law_tools = risk_info.get("risk_level") == "low" and "company_search" in guardrails
    # Tier 2 + 금액 + MCP preflight 완료 시: 법령은 이미 컨텍스트에 주입됨
    # → LLM이 법령 도구를 추가 호출하지 않도록 제거 (종합·작문에 집중)
    skip_company_tools = False
    if query_tier == 2 and amount_detected is not None and mandatory_mcp_executed:
        skip_law_tools = True
        # 업체 7개도 사전 호출 완료 → LLM에서 업체 도구도 제거 (중복 호출 방지)
        skip_company_tools = True
        print("  [TOOL_FILTER] tier=2 사전호출 완료 → 법령+업체 도구 제거, LLM은 종합·작문만 수행")
    if tool_loop_gate_writer_only_enforced:
        skip_law_tools = True
        skip_company_tools = True
        _current_tool_loop_gate_meta["tool_loop_gate_enforced"] = True
        print("  [TOOL-LOOP-GATE] enforce writer-only → all tools removed for this turn", flush=True)
    else:
        _current_tool_loop_gate_meta.setdefault("tool_loop_gate_enforced", False)
    law_tools_to_skip = ["chain_full_research", "chain_action_basis", "search_law", "get_law_text", "search_interpretations", "get_annexes", "chain_procedure_detail", "chain_ordinance_compare", "chain_document_review", "chain_law_system", "search_admin_rule", "get_admin_rule", "chain_amendment_track"]
    company_tools_to_skip = company_tools + shopping_tools + policy_company_tools + product_tools
    
    all_funcs = law_tools[0].function_declarations
    filtered_funcs = []
    for f in all_funcs:
        # 법령 도구 스킵
        if skip_law_tools and f.name in law_tools_to_skip:
            continue
        # 업체 도구 스킵 (tier=2 사전호출 완료 시)
        if skip_company_tools and f.name in company_tools_to_skip:
            continue
        # 업체검색은 guardrails에 있을 때만 허용 (기존 로직 유지)
        if not skip_company_tools:
            if f.name in company_tools:
                if "company_search" not in guardrails:
                    continue
            elif f.name in shopping_tools:
                if "mas_shopping_mall" not in guardrails and "company_search" not in guardrails:
                    continue
        filtered_funcs.append(f)

    if not LLM_TOOL_LOOP_ENABLED:
        if filtered_funcs:
            print(
                f"  [LLM-TOOL-LOOP] disabled by LLM_TOOL_LOOP_ENABLED=false; "
                f"removing {len(filtered_funcs)} function tools. Preflight evidence/context remains.",
                flush=True,
            )
        filtered_funcs = []
        _current_tool_loop_gate_meta["tool_loop_gate_enforced"] = True
        _current_tool_loop_gate_meta.setdefault("tool_loop_gate_reasons", [])
        if isinstance(_current_tool_loop_gate_meta.get("tool_loop_gate_reasons"), list):
            _current_tool_loop_gate_meta["tool_loop_gate_reasons"].append("llm_tool_loop_disabled_by_config")
    
    # 도구가 0개가 되면 LLM이 텍스트 생성만 수행 (도구 호출 불가)
    if filtered_funcs:
        dynamic_tools = [types.Tool(function_declarations=filtered_funcs)]
    else:
        dynamic_tools = []
    _current_llm_payload_meta["llm_payload_tool_count_available"] = len(filtered_funcs)
    _current_llm_payload_meta["llm_tool_loop_enabled"] = LLM_TOOL_LOOP_ENABLED
    _current_llm_payload_meta["llm_internal_tools_disabled"] = not LLM_TOOL_LOOP_ENABLED

    answer_budget, answer_budget_reason = _answer_thinking_budget_for(
        user_message,
        base_budget=GEMINI_COMPLEX_THINKING_BUDGET,
    )
    _current_llm_payload_meta["llm_answer_thinking_budget"] = answer_budget
    _current_llm_payload_meta["llm_answer_thinking_budget_reason"] = answer_budget_reason
    print(
        f"  [ANSWER-BUDGET] main budget={answer_budget} reason={answer_budget_reason}",
        flush=True,
    )

    config = types.GenerateContentConfig(
        system_instruction=assembled.core_prompt,  # Core만 (불변)
        tools=dynamic_tools,
        temperature=0.1,
        thinking_config=_thinking_config_for(answer_budget),
    )

    # 대화 이력 + dynamic context
    contents = []
    for h in history:
        contents.append(types.Content(
            role=h["role"],
            parts=[types.Part.from_text(text=h["text"])]
        ))

    # Dynamic context + 사용자 질문은 하나의 user message로
    contents.append(types.Content(
        role="user",
        parts=[types.Part.from_text(text=dynamic_context)]
    ))
    _current_llm_payload_meta["llm_payload_initial_contents_chars"] = _content_text_chars(contents)
    _current_llm_payload_meta["llm_payload_max_contents_chars"] = _current_llm_payload_meta["llm_payload_initial_contents_chars"]

    # ─── 7. Function-calling loop (MAX_TOOL_CALL_ROUNDS=3) ───
    called_tools = set()  # 중복 호출 차단
    all_tool_results = []  # timeout/fail-closed 추적용
    mcp_was_called = False
    product_prefetch_executed = False  # 혁신/기술개발 강제 prefetch 여부

    # ── Deterministic Pre-router: 혁신제품/기술개발제품 키워드 감지 시 tool 강제 호출 ──
    _innovation_keywords = ["혁신제품", "혁신시제품"]
    _tech_keywords = ["기술개발제품", "우수조달물품", "NEP", "GS", "NET", "기술개발"]
    msg_lower = user_message
    
    forced_tool_name = None
    forced_tool_query = user_message  # 기본값
    import re as _re_pf
    if any(kw in msg_lower for kw in _innovation_keywords):
        forced_tool_name = "search_innovation_products"
        # 품목명 추출 시도
        for kw in _innovation_keywords:
            msg_lower = msg_lower.replace(kw, "")
        # 남은 명사 중 검색어 추출
        cleaned = _re_pf.sub(r"[^가-힣a-zA-Z0-9]", " ", msg_lower).strip()
        forced_tool_query = cleaned if cleaned else user_message
    elif any(kw in msg_lower for kw in _tech_keywords):
        forced_tool_name = "search_tech_development_products"
        for kw in _tech_keywords:
            msg_lower = msg_lower.replace(kw, "")
        cleaned = _re_pf.sub(r"[^가-힣a-zA-Z0-9]", " ", msg_lower).strip()
        forced_tool_query = cleaned if cleaned else user_message

    if forced_tool_name:
        print(f"  [PRODUCT_PREFETCH] {forced_tool_name}(query='{forced_tool_query}')")
        import time as _time_pf
        _pf_start = _time_pf.time()
        try:
            class _MockFC:
                def __init__(self, name, query):
                    self.name = name
                    self.args = {"query": query}
            pf_result_str = _execute_function_call(_MockFC(forced_tool_name, forced_tool_query))
            _pf_elapsed = int((_time_pf.time() - _pf_start) * 1000)
            pf_status = "success"
            if any(kw in pf_result_str for kw in ["[TIMEOUT]", "TIMEOUT", "응답 지연"]):
                pf_status = "timeout"
            elif any(kw in pf_result_str for kw in ["[FAILED]", "오류"]):
                pf_status = "failed"
            
            pf_tool_result = {
                "tool_name": forced_tool_name, "status": pf_status,
                "result": pf_result_str, "elapsed_ms": _pf_elapsed,
            }
            # JSON 파싱하여 structured_rows를 상위 레벨로 병합
            try:
                parsed = json.loads(pf_result_str)
                if isinstance(parsed, dict):
                    for k in ["structured_rows", "product_sample_rows"]:
                        if k in parsed:
                            pf_tool_result[k] = parsed[k]
            except (json.JSONDecodeError, TypeError):
                pass
            
            all_tool_results.append(pf_tool_result)
            product_prefetch_executed = True
            called_tools.add(f"prefetch:{forced_tool_name}")
            print(f"  [PRODUCT_PREFETCH] status={pf_status} elapsed={_pf_elapsed}ms")
        except Exception as e:
            print(f"  [PRODUCT_PREFETCH] Failed: {e}")
            all_tool_results.append({
                "tool_name": forced_tool_name, "status": "failed",
                "result": str(e), "elapsed_ms": 0,
            })

    # 광범위 질문인 경우 Gemini 1차 호출조차 생략하고 즉시 조기 종료 (초고속 Fail-closed)
    if intent_result.mcp_required and any(kw in user_message for kw in ["규정", "다 어떻게", "모두 알려"]):
        print("  [PREFETCH] Broad question detected before Gemini — immediate early exit")
        api_status.mcp_status = "skipped"
        # intercepts에 broad question 플래그 전달 (검증 스크립트용)
        log_routing(broad_question_early_exit=True)
        all_tool_results.append({
            "tool_name": "chain_full_research", "status": "skipped",
            "result": "질문 범위가 너무 넓어 상세 검색이 생략되었습니다.", "elapsed_ms": 0,
        })
        
        fallback_answer = (
            "질문의 범위가 넓어 법령 조회 범위를 제한하여 조건부 안내를 드립니다.\n\n"
            "⚠️ **확인 필요 사항**\n"
            "- 법령 조회가 완료되지 않아 금액 기준과 1인 견적 가능 여부는 확정할 수 없습니다. "
            "다만 검토 구조는 다음과 같습니다.\n"
            "- 수의계약 대상 업체 선정 시 지역상품 구매 확대방향을 고려하시기 바랍니다.\n"
            "- 실제 업체검색은 품목·과업·공종이 특정된 뒤 수행하는 것이 적절합니다.\n"
            "- 상세한 수의계약 가능 여부는 구체적인 사안에 따라 관련 법령 조회가 필요합니다."
        )
        mcp_was_called = True
        answer, history = _finalize_answer(fallback_answer, history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
            "model_used": MODEL_ID,
            "fallback_used": False,
            "fallback_reason": "",
            "retry_count": 0,
            "core_prompt_hash": assembled.core_prompt_hash if 'assembled' in locals() and getattr(assembled, 'core_prompt_hash', '') else __import__('hashlib').sha256(b"deterministic_broad_question_fallback_core").hexdigest(),
            "prompt_prefix_hash": assembled.prompt_prefix_hash if 'assembled' in locals() and getattr(assembled, 'prompt_prefix_hash', '') else __import__('hashlib').sha256(b"deterministic_broad_question_fallback_prefix").hexdigest()[:16],
            "company_table_allowed": "company_search" in guardrails if 'guardrails' in locals() else False,
            "rag_elapsed_ms": rag_elapsed_ms if 'rag_elapsed_ms' in locals() else 0,
            "model_elapsed_ms": int((time.time() - model_start) * 1000) if 'model_start' in locals() else 0,
            "tool_call_count": len(all_tool_results)
        })
        return answer, history

    # ── 모델 라우팅: 위험도 기반 모델 선택 ──
    from policies.model_routing_policy import classify_risk, build_routing_log
    intent_labels = [c[0] for c in getattr(api_status, 'intent_candidates', [])] if hasattr(api_status, 'intent_candidates') else []
    risk_info = classify_risk(user_message, intent_labels)
    model_to_use = risk_info["model_primary"]
    print(f"  [ROUTING] risk_level={risk_info['risk_level']} model_primary={model_to_use} triggers={risk_info['high_risk_triggers'][:3]}", flush=True)

    fallback_used = False
    fallback_reason = ""
    total_retries = 0
    malformed_function_call_detected = False
    function_call_retry_count = 0
    function_call_final_status = "not_detected"

    model_start = time.time()
    
    amount_detected = _parse_amount(user_message)
    current_route_plan = route_plan if 'route_plan' in locals() else None
    current_intent_frame = intent_frame if 'intent_frame' in locals() else None
    simple_amount_bypass_required = (
        amount_detected is not None
        and (
            (
                current_route_plan is not None
                and _route_plan_execution_mode(current_route_plan) == "evidence_prefetch"
                and getattr(current_route_plan, "company_search_mode", "none") == "none"
                and not getattr(current_intent_frame, "item_name", "")
            )
            or (current_route_plan is None and query_tier == 1)
        )
    )
    if simple_amount_bypass_required:
        # 단순 금액 질문(구체 품목 없음)은 실행계획 기준으로 템플릿/후처리 경로를 유지한다.
        if progress_callback:
            progress_callback("⚡ [Bypass] 모델 본문 생성 우회 및 템플릿 처리 중...")

        return _finalize_answer("", history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
            "model_used": "bypass_tier_1_2",
            "tier_resolved": query_tier,
            "mandatory_mcp_plan": mandatory_mcp_plan,
            "mandatory_mcp_executed": mandatory_mcp_executed,
            "mandatory_mcp_missing": mandatory_mcp_missing,
            "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
            "rag_elapsed_ms": rag_elapsed_ms if 'rag_elapsed_ms' in locals() else 0,
            "model_elapsed_ms": 0,
            "tool_call_count": len(all_tool_results),
            "legal_basis_cache_used": cache_stats.get("legal_basis_cache_used", False) if 'cache_stats' in locals() else False,
            "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0) if 'cache_stats' in locals() else 0,
            "legal_basis_cache_miss_count": cache_stats.get("legal_basis_cache_miss_count", 0) if 'cache_stats' in locals() else 0,
            "mcp_called_for_cache_miss": cache_stats.get("mcp_called_for_cache_miss", False) if 'cache_stats' in locals() else False,
            "mcp_called_for_freshness": cache_stats.get("mcp_called_for_freshness", False) if 'cache_stats' in locals() else False,
            "cache_status": cache_stats.get("cache_status", "") if 'cache_stats' in locals() else "",
        })

    # ── 금액+품목/지역구매 실행계획: 멀티 라우트 사전 검색 후 LLM에 위임 ──
    if _should_run_multi_route_prefetch_from_route_plan(
        current_route_plan,
        query_tier,
        amount_detected,
    ):
        should_prefetch_company, query, prefetch_reason = _should_prefetch_company_routes(
            user_message,
            legacy_router_result if 'legacy_router_result' in locals() else None,
            intent_rag_decision if 'intent_rag_decision' in locals() else None,
            route_plan if 'route_plan' in locals() else None,
        )
        legacy_router_meta["company_prefetch_enabled"] = should_prefetch_company
        legacy_router_meta["company_prefetch_query"] = query
        legacy_router_meta["company_prefetch_reason"] = prefetch_reason
        normalized_prefetch_item = normalize_item_query(user_message, query)
        legacy_router_meta["company_prefetch_canonical_item"] = normalized_prefetch_item.canonical_name or query
        legacy_router_meta["company_prefetch_search_terms"] = normalized_prefetch_item.search_terms or ([query] if query else [])
        legacy_router_meta["company_prefetch_item_normalization_reason"] = normalized_prefetch_item.reason
        contract_object_for_prefetch = _get_router_contract_object(
            legacy_router_result if 'legacy_router_result' in locals() else None,
            user_message,
        )
        legacy_router_meta["company_prefetch_contract_object"] = contract_object_for_prefetch
        print(
            "  [MULTI-ROUTE-GATE] "
            f"enabled={should_prefetch_company} query='{query}' "
            f"canonical='{legacy_router_meta['company_prefetch_canonical_item']}' "
            f"object={contract_object_for_prefetch} reason={prefetch_reason}",
            flush=True,
        )

        if progress_callback:
            if should_prefetch_company:
                progress_callback("🔍 [Multi-Route] 구매 경로별 업체 사전 검색 중...")
            else:
                progress_callback("🔎 구체 품목이 없어 업체 검색은 생략하고 법령 검토를 진행합니다.")

        import concurrent.futures

        def run_mock_tool(tool_name, query_arg):
            start = time.time()
            mock_call = MockFunctionCall(tool_name, {"query": query_arg})
            res = _execute_function_call(mock_call)
            elapsed = int((time.time() - start) * 1000)
            return {
                "tool_name": tool_name,
                "status": "success" if "error" not in res else "failed",
                "result": res,
                "elapsed_ms": elapsed
            }

        def run_mock_tool_product(tool_name, product_arg):
            """product_name 파라미터를 사용하는 도구용."""
            start = time.time()
            mock_call = MockFunctionCall(tool_name, {"product_name": product_arg})
            res = _execute_function_call(mock_call)
            elapsed = int((time.time() - start) * 1000)
            return {
                "tool_name": tool_name,
                "status": "success" if "error" not in res else "failed",
                "result": res,
                "elapsed_ms": elapsed
            }

        if should_prefetch_company:
            # 멀티 라우트 검색:
            # - 물품: 품목 + 쇼핑몰 + 정책기업 + 인증/혁신제품
            # - 용역/공사: 면허·업종/공종 + 정책기업 중심
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = []
                if contract_object_for_prefetch == "goods":
                    futures.extend([
                        executor.submit(run_mock_tool, "search_shopping_mall", query),
                        executor.submit(run_mock_tool, "search_local_company_by_product", query),
                        executor.submit(run_mock_tool_product, "search_certified_product", query),
                        executor.submit(run_mock_tool_product, "search_innovation_product", query),
                    ])
                else:
                    futures.append(executor.submit(run_mock_tool, "search_local_company_by_license", query))

                futures.extend([
                    executor.submit(run_mock_tool, "search_company_by_policy", "여성기업"),
                    executor.submit(run_mock_tool, "search_company_by_policy", "사회적기업"),
                    executor.submit(run_mock_tool, "search_company_by_policy", "장애인기업"),
                ])
                for f in concurrent.futures.as_completed(futures):
                    all_tool_results.append(f.result())

            all_tool_results = _filter_company_tool_results_by_item(
                all_tool_results,
                user_message,
                legacy_router_meta,
            )

            route_cards_for_prefetch = build_purchase_route_cards(
                amount=amount_detected,
                item_name=legacy_router_meta["company_prefetch_canonical_item"] or query,
                contract_object=contract_object_for_prefetch,
                agency_type=_normalize_agency_type(agency_type) if agency_type else None,
                tool_results=all_tool_results,
            )
            route_candidate_display_options = derive_candidate_table_display_options(route_cards_for_prefetch)
            route_guidance_context = format_purchase_route_guidance_for_llm(
                amount=amount_detected,
                item_name=legacy_router_meta["company_prefetch_canonical_item"] or query,
                contract_object=contract_object_for_prefetch,
                agency_type=_normalize_agency_type(agency_type) if agency_type else None,
                tool_results=all_tool_results,
            )
            catalog_guidance_context = format_catalog_matches_for_llm(
                user_message,
                contract_object=contract_object_for_prefetch,
                agency_type=_normalize_agency_type(agency_type) if agency_type else None,
            )
            from policies.complex_judgment_cards import (
                build_complex_judgment_cards,
                render_complex_judgment_cards,
            )
            complex_judgment_cards = build_complex_judgment_cards(
                user_message=user_message,
                amount=amount_detected,
                item_name=legacy_router_meta["company_prefetch_canonical_item"] or query,
                contract_object=contract_object_for_prefetch,
                agency_type=_normalize_agency_type(agency_type) if agency_type else None,
                tool_results=all_tool_results,
                evidence_cards=evidence_cards if 'evidence_cards' in locals() else [],
            )
            complex_judgment_context = render_complex_judgment_cards(complex_judgment_cards)

            # 사전 검색 결과를 LLM 컨텍스트에 주입 (LLM이 분석·그룹핑)
            prefetch_parts = [
                route_guidance_context,
                catalog_guidance_context,
                complex_judgment_context,
                practice_manual_context,
                pps_qa_context,
                "\n\n[사전 검색된 업체 데이터 — 아래 데이터를 기반으로 구매 경로별 업체를 그룹핑하여 안내하라]",
                f"- 표준 품목명: {legacy_router_meta['company_prefetch_canonical_item'] or query}",
                f"- 보조 검색어: {', '.join(legacy_router_meta['company_prefetch_search_terms'][:6]) or query}",
            ]
            for tr in all_tool_results:
                tool_name = tr.get("tool_name", "unknown")
                result_text = tr.get("result", "")
                if isinstance(result_text, str) and len(result_text) > 10:
                    prefetch_parts.append(f"\n--- {tool_name} 결과 ---\n{result_text[:3000]}")
            prefetch_context = "\n".join(prefetch_parts)

            # 기존 contents의 마지막 user 메시지에 사전 검색 결과를 추가
            if contents and contents[-1].role == "user":
                original_text = contents[-1].parts[0].text
                contents[-1] = types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=original_text + prefetch_context)]
                )

        print(f"  [MULTI-ROUTE] tier=2, amount={amount_detected}, query='{query}', prefetched={len(all_tool_results)} tools", flush=True)
        if should_prefetch_company and os.getenv("BYPASS_MULTI_ROUTE_LLM", "true").lower() == "true":
            company_sections = []
            policy_company_sections_skipped = False
            hidden_prefetch_candidate_types = set(
                (locals().get("route_candidate_display_options") or {}).get("hidden_candidate_types", [])
            )
            for tr in all_tool_results:
                tool_name = tr.get("tool_name", "")
                if not (
                    "company" in tool_name
                    or "shopping_mall" in tool_name
                    or "certified_product" in tool_name
                    or "innovation_product" in tool_name
                ):
                    continue
                if "company_by_policy" in tool_name and "policy_company" in hidden_prefetch_candidate_types:
                    policy_company_sections_skipped = True
                    continue
                result_text = str(tr.get("result", "") or "").strip()
                if result_text:
                    company_sections.append(f"#### {_company_tool_label(tool_name)}\n{result_text[:2500]}")

            route_answer_parts = [
                "### 판단 요약",
                f"- 질문 조건은 **{_display_amount_for_answer(amount_detected, user_message)} 규모의 {legacy_router_meta['company_prefetch_canonical_item'] or query} 구매 검토**입니다.",
                "- 일반 소액 수의계약만으로 단정하기보다, 금액 기준과 품목 특성을 함께 보면서 지역상품 구매 경로를 나누어 검토하는 편이 안전합니다.",
                "",
                "### 구매 경로 검토",
                _clean_route_guidance_for_answer(route_guidance_context) or "- 지역제한, 종합쇼핑몰/MAS, 정책기업, 인증제품 여부를 함께 확인하세요.",
                _clean_catalog_guidance_for_answer(catalog_guidance_context),
                render_practice_manual_cards_for_answer(practice_manual_cards),
                render_pps_qa_cards_for_answer(pps_qa_cards),
                "",
                "### 업체 후보 및 확인 포인트",
            ]
            if company_sections:
                route_answer_parts.extend(company_sections)
                if policy_company_sections_skipped:
                    route_answer_parts.append(
                        "- 정책기업 1인 견적 경로는 금액상 우선 제외되어 정책기업 전용 후보표는 생략했습니다. "
                        "후보 업체 상세조회에서 여성기업ㆍ장애인기업ㆍ사회적기업 등 정책기업 여부를 별도 확인하세요."
                    )
            else:
                route_answer_parts.append("- 현재 사전검색 결과에서 바로 표시할 업체 후보가 부족합니다. 품목명 또는 세부 규격을 더 구체화해 재검색하세요.")
            route_answer_parts.extend([
                "",
                "### 다음 확인사항",
                "- 후보 업체의 조달등록, 종합쇼핑몰 등록, 정책기업 여부, 인증제품 상태, 세부품명 일치 여부를 계약 전 확인하세요.",
                "- 이 답변은 내부 법령 DB와 업체 API 사전조회 결과를 조합한 실무 검토용 안내입니다.",
            ])

            api_status = ApiStatus()
            _multi_route_fast_meta = {
                "model_used": "deterministic_internal_law_db_plus_company_api",
                "model_decision_reason": "multi_route_prefetch_fast_answer",
                "tier_resolved": query_tier,
                "fast_track_applied": False,
                "deterministic_template_used": True,
                "amount_rewrite_bypass": True,
                "company_table_allowed": True,
                "legal_conclusion_allowed": True,
                "candidate_table_source": "company_api_prefetch",
                "answer_schema_version": "multi_route_fast_answer_v1",
                "source_status": "mcp_preflight_and_company_api_success",
                "rag_elapsed_ms": rag_elapsed_ms if 'rag_elapsed_ms' in locals() else 0,
                "model_elapsed_ms": 0,
                "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
                "tool_call_count": len(all_tool_results),
                "direct_legal_basis_count": len(mandatory_mcp_executed),
                "mandatory_mcp_plan": mandatory_mcp_plan,
                "mandatory_mcp_executed": mandatory_mcp_executed,
                "mandatory_mcp_missing": mandatory_mcp_missing,
                "evidence_cards": evidence_cards if 'evidence_cards' in locals() else [],
                "evidence_card_count": cache_stats.get("evidence_card_count", 0) if 'cache_stats' in locals() else 0,
                "internal_db_hit_count": cache_stats.get("internal_db_hit_count", 0) if 'cache_stats' in locals() else 0,
                "external_mcp_fallback_count": cache_stats.get("external_mcp_fallback_count", 0) if 'cache_stats' in locals() else 0,
                "evidence_missing_count": cache_stats.get("evidence_missing_count", 0) if 'cache_stats' in locals() else 0,
                "company_search_status": "success",
                "company_prefetch_query": query,
                "company_prefetch_canonical_item": legacy_router_meta["company_prefetch_canonical_item"],
                "company_prefetch_contract_object": contract_object_for_prefetch,
                "purchase_route_hidden_candidate_types": list(hidden_prefetch_candidate_types),
                "purchase_route_preferred_candidate_order": (
                    locals().get("route_candidate_display_options") or {}
                ).get("preferred_candidate_order", []),
                "purchase_route_policy_company_table_hidden": "policy_company" in hidden_prefetch_candidate_types,
                "purchase_route_card_count": len(locals().get("route_cards_for_prefetch") or []),
                "complex_judgment_cards": complex_judgment_cards,
                "complex_judgment_card_count": len(complex_judgment_cards),
                "practice_manual_card_count": len(practice_manual_cards),
                "pps_qa_card_count": len(pps_qa_cards),
                "skip_citation_verify": True,
            }
            return _finalize_answer(
                "\n".join(part for part in route_answer_parts if part is not None),
                history,
                user_message,
                all_tool_results,
                api_status,
                progress_callback,
                generation_meta=_multi_route_fast_meta,
            )

        # bypass 하지 않고 아래 LLM 루프로 fall-through

    # LLM 루프 전체 경과시간 제한.  긴 루프는 답변 품질보다 타임아웃 위험을 키우므로
    # 모델 호출과 전체 루프를 모두 벽시계 기준으로 제한한다.
    from policies.timeout_policy import FAIL_TO_CACHE as _FTC, get_timeout as _get_tool_timeout
    _loop_max_sec = float(os.getenv("LLM_TOOL_LOOP_MAX_SEC", "12" if _FTC else "30"))
    _model_turn_timeout_sec = float(os.getenv("LLM_TOOL_MODEL_TIMEOUT_SEC", "18"))
    _model_retry_max = max(1, int(os.getenv("LLM_TOOL_RETRY_MAX", "2")))
    _model_retry_base_sec = max(0.0, float(os.getenv("LLM_TOOL_RETRY_BASE_SEC", "1")))
    _loop_start = time.time()

    for round_i in range(MAX_TOOL_CALL_ROUNDS):
        # 전체 루프 경과시간 체크
        _loop_elapsed = time.time() - _loop_start
        if _loop_elapsed > _loop_max_sec:
            print(f"  [LOOP_DEADLINE] {_loop_elapsed:.1f}s > {_loop_max_sec}s. Breaking.")
            break
        # API 호출 (429 재시도, Malformed 재시도 및 Fallback)
        response = None
        last_err = None
        
        # 내부 재시도 루프: 503/429는 짧게 재시도하고, 모델 timeout은 즉시 fallback으로 넘긴다.
        for retry in range(_model_retry_max):
            total_retries += 1
            try:
                remaining_loop_sec = max(1.0, _loop_max_sec - (time.time() - _loop_start))
                current_contents_chars = _content_text_chars(contents)
                _current_llm_payload_meta["llm_payload_model_round_count"] = max(
                    int(_current_llm_payload_meta.get("llm_payload_model_round_count", 0) or 0),
                    round_i + 1,
                )
                _current_llm_payload_meta[f"llm_payload_round_{round_i+1}_input_chars"] = current_contents_chars
                _current_llm_payload_meta["llm_payload_max_contents_chars"] = max(
                    int(_current_llm_payload_meta.get("llm_payload_max_contents_chars", 0) or 0),
                    current_contents_chars,
                )
                response = _generate_content_bounded(
                    model=model_to_use,
                    contents=contents,
                    config=config,
                    timeout_sec=min(_model_turn_timeout_sec, remaining_loop_sec),
                    label=f"tool_loop_round_{round_i+1}",
                )
                
                # Malformed 검사
                candidate = response.candidates[0]
                if candidate.content is None or not candidate.content.parts:
                    reason = getattr(candidate, 'finish_reason', None)
                    if reason and "MALFORMED_FUNCTION_CALL" in str(reason):
                        if function_call_retry_count < 1:
                            function_call_retry_count += 1
                            print(f"  [WARNING] Empty response. finish_reason=MALFORMED_FUNCTION_CALL. Retrying ({function_call_retry_count}/1)...", flush=True)
                            time.sleep(1)
                            continue # 다시 API 호출
                        else:
                            print("  [WARNING] Empty response. finish_reason=MALFORMED_FUNCTION_CALL after retry.")
                            malformed_function_call_detected = True
                            function_call_final_status = "malformed_fail_closed"
                            break # 에러 누적 후 for retry 루프 탈출
                
                # 정상 응답이고 재시도 이력이 있다면 상태 업데이트
                if function_call_retry_count > 0 and not malformed_function_call_detected:
                    function_call_final_status = "success_after_retry"
                break # 정상 응답 또는 다른 finish_reason이면 for retry 루프 탈출
            except Exception as api_err:
                last_err = api_err
                err_msg = str(api_err)
                if isinstance(api_err, TimeoutError) or "model call exceeded" in err_msg:
                    _current_llm_payload_meta["llm_payload_model_timeout_count"] = int(
                        _current_llm_payload_meta.get("llm_payload_model_timeout_count", 0) or 0
                    ) + 1
                    _current_llm_payload_meta.setdefault("llm_payload_model_error_statuses", []).append("local_model_timeout")
                    print(f"  [API] model turn timeout: {err_msg}", flush=True)
                    break
                if any(kw in err_msg for kw in ["499", "CANCELLED", "cancelled", "504", "DEADLINE_EXCEEDED", "timed out", "timeout"]):
                    _current_llm_payload_meta["llm_payload_model_timeout_count"] = int(
                        _current_llm_payload_meta.get("llm_payload_model_timeout_count", 0) or 0
                    ) + 1
                    _current_llm_payload_meta.setdefault("llm_payload_model_error_statuses", []).append("remote_model_timeout")
                    print(f"  [API] model/server timeout: {err_msg[:200]}", flush=True)
                    break
                if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
                    if "pro" in model_to_use:
                        print("  [API] 429 Quota Exhausted. Falling back to Flash model.", flush=True)
                        model_to_use = "gemini-2.5-flash"
                        fallback_used = True
                        fallback_reason = "429_Quota_Exhausted"
                        continue # 즉시 Flash로 재시도
                
                if any(kw in err_msg for kw in ["429", "RESOURCE_EXHAUSTED", "503"]):
                    _current_llm_payload_meta.setdefault("llm_payload_model_error_statuses", []).append("retryable_api_error")
                    wait_sec = _model_retry_base_sec * (retry + 1)
                    print(f"  [API] Retry {retry+1}/{_model_retry_max} - waiting {wait_sec}s...", flush=True)
                    time.sleep(wait_sec)
                else:
                    _current_llm_payload_meta.setdefault("llm_payload_model_error_statuses", []).append("non_retryable_api_error")
                    raise

        if response is None:
            import hashlib as _hl_fb
            _fb_core_hash = assembled.core_prompt_hash if 'assembled' in locals() and getattr(assembled, 'core_prompt_hash', '') else _hl_fb.sha256(b"deterministic_company_search_fallback_core").hexdigest()
            _fb_prefix_hash = assembled.prompt_prefix_hash if 'assembled' in locals() and getattr(assembled, 'prompt_prefix_hash', '') else _hl_fb.sha256(b"deterministic_company_search_fallback_prefix").hexdigest()[:16]
            _last_err_str = str(last_err or "")
            if any(kw in _last_err_str for kw in ["504", "DEADLINE_EXCEEDED", "timed out", "timeout"]):
                _fb_err_type = "MODEL_TIMEOUT"
            elif any(kw in _last_err_str for kw in ["503", "UNAVAILABLE"]):
                _fb_err_type = "503_UNAVAILABLE"
            else:
                _fb_err_type = "API_FAILURE"
            if "company_search" in guardrails:
                print("  [FALLBACK] API call failed. Using deterministic fallback for company_search.")
                class _MockFC:
                    def __init__(self, name, query):
                        self.name = name; self.args = {"query": query}
                try:
                    fallback_res = _execute_function_call(_MockFC("search_local_company_by_product", user_message))
                    all_tool_results.append({
                        "tool_name": "search_local_company_by_product", "status": "success",
                        "result": fallback_res, "elapsed_ms": 100
                    })
                    fast_track_msg = "⚠️ 시스템 연동 지연으로 간편 검색 결과를 바로 제공합니다. 판단 및 계약 진행 전 우선 관련 법령 및 수의계약 가능 여부를 체계적으로 검토하시기 바랍니다."
                    ans, hist = _finalize_answer(fast_track_msg, history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
                        "model_used": model_to_use,
                        "fallback_used": True,
                        "fallback_reason": f"gemini_api_{_fb_err_type.lower()}_company_search_fallback",
                        "retry_count": total_retries,
                        "risk_level": risk_info.get("risk_level", "unknown"),
                        "high_risk_triggers": risk_info.get("high_risk_triggers", []),
                        "model_decision_reason": "company_search_api_fallback",
                        "malformed_function_call_detected": False,
                        "function_call_retry_count": 0,
                        "function_call_final_status": "success",
                        "fast_track_applied": True,
                        "deterministic_template_used": True,
                        "company_table_allowed": True,
                        "core_prompt_hash": _fb_core_hash,
                        "prompt_prefix_hash": _fb_prefix_hash,
                        "api_error_detected": True,
                        "api_error_type": _fb_err_type,
                        "selected_guardrails": list(guardrails) if 'guardrails' in locals() else ["common_procurement", "company_search", "item_purchase"],
                    })
                    return ans, hist
                except Exception as e:
                    raise last_err or Exception("API call failed after retries")
            else:
                # 503 등 API 실패 시, MCP Preflight 데이터가 있으면 fallback 답변 생성
                if 'mcp_context' in locals() and mcp_context:
                    print(f"  [FALLBACK] Gemini 503. MCP 법령 데이터로 fallback 답변 생성.")
                    fallback_tool_results = list(all_tool_results)
                    if not fallback_tool_results:
                        fallback_tool_results.append({
                            "tool_name": "chain_full_research",
                            "status": "success",
                            "result": mcp_context,
                            "elapsed_ms": mcp_preflight_elapsed_ms if 'mcp_preflight_elapsed_ms' in locals() else 0,
                            "tool_args": {"query": user_message},
                            "raw_result_chars": len(mcp_context or ""),
                            "llm_result_chars": len(mcp_context or ""),
                        })
                    fallback_msg = _build_grounded_case_timeout_fallback(user_message, mcp_context)
                    ans, hist = _finalize_answer(fallback_msg, history, user_message, fallback_tool_results, api_status, progress_callback, generation_meta={
                        "model_used": model_to_use,
                        "fallback_used": True,
                        "fallback_reason": f"gemini_api_{_fb_err_type.lower()}_mcp_fallback",
                        "retry_count": total_retries,
                        "risk_level": risk_info.get("risk_level", "unknown"),
                        "high_risk_triggers": risk_info.get("high_risk_triggers", []),
                        "model_decision_reason": "gemini_503_mcp_data_fallback",
                        "deterministic_template_used": True,
                        "amount_rewrite_bypass": True,
                        "preflight_grounded_fallback": True,
                        "source_status": "mcp_preflight_success",
                        "direct_legal_basis_count": len(mandatory_mcp_executed) if 'mandatory_mcp_executed' in locals() else 0,
                        "mandatory_mcp_plan": mandatory_mcp_plan if 'mandatory_mcp_plan' in locals() else [],
                        "mandatory_mcp_executed": mandatory_mcp_executed if 'mandatory_mcp_executed' in locals() else [],
                        "mandatory_mcp_missing": mandatory_mcp_missing if 'mandatory_mcp_missing' in locals() else [],
                        "evidence_cards": evidence_cards if 'evidence_cards' in locals() else [],
                        "evidence_card_count": cache_stats.get("evidence_card_count", 0) if 'cache_stats' in locals() else 0,
                        "internal_db_hit_count": cache_stats.get("internal_db_hit_count", 0) if 'cache_stats' in locals() else 0,
                        "external_mcp_fallback_count": cache_stats.get("external_mcp_fallback_count", 0) if 'cache_stats' in locals() else 0,
                        "evidence_missing_count": cache_stats.get("evidence_missing_count", 0) if 'cache_stats' in locals() else 0,
                        "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms if 'mcp_preflight_elapsed_ms' in locals() else 0,
                        "core_prompt_hash": _fb_core_hash,
                        "prompt_prefix_hash": _fb_prefix_hash,
                        "api_error_detected": True,
                        "api_error_type": _fb_err_type,
                        "selected_guardrails": list(guardrails) if 'guardrails' in locals() else ["common_procurement"],
                        "legacy_gemini_intent_router": legacy_router_meta if 'legacy_router_meta' in locals() else {"status": "not_available"},
                    })
                    return ans, hist
                raise last_err or Exception("API call failed after retries")

        candidate = response.candidates[0]

        # 빈 응답 처리
        if candidate.content is None or not candidate.content.parts:
            reason = getattr(candidate, 'finish_reason', None)
            if reason and "SAFETY" in str(reason):
                return "⚠️ AI 안전 정책에 의해 답변이 제한됩니다.", history
            
            if malformed_function_call_detected:
                # Fail-closed 유도를 위해 가상의 실패 도구 호출을 넣고 전체 루프 탈출
                all_tool_results.append({
                    "tool_name": "malformed_function_call_fallback", "status": "failed",
                    "result": "[FAILED] MALFORMED_FUNCTION_CALL 발생", "elapsed_ms": 0,
                })
                break

            return "⚠️ 답변을 생성하지 못했습니다. 질문을 다시 작성해 주세요.", history

        # Function call 수집
        function_calls = [p.function_call for p in candidate.content.parts if p.function_call]

        if function_calls:
            contents.append(candidate.content)

            # 중복 호출 필터링
            unique_calls = []
            for fc in function_calls:
                call_key = f"{fc.name}:{json.dumps(dict(fc.args) if fc.args else {}, sort_keys=True)}"
                if call_key not in called_tools:
                    called_tools.add(call_key)
                    unique_calls.append(fc)
                else:
                    print(f"  [SKIP] Duplicate tool call: {fc.name}")

            if not unique_calls:
                # 모든 호출이 중복이면 마지막 라운드로 강제 진행
                continue

            # 병렬 실행 (timeout_policy 적용)
            if progress_callback:
                progress_callback("🔍 법령 검색 중...")

            from concurrent.futures import ThreadPoolExecutor
            response_parts = []

            with ThreadPoolExecutor(max_workers=len(unique_calls)) as pool:
                futures = {}
                for idx, fc in enumerate(unique_calls):
                    print(f"  [tool] R{round_i+1}: {fc.name}({dict(fc.args) if fc.args else {}})")
                    if progress_callback:
                        label = TOOL_LABELS.get(fc.name, "🔍 검색 중")
                        progress_callback(label)

                    mcp_was_called = True
                    tool_start = time.time()
                    call_key = f"{idx}:{fc.name}:{json.dumps(dict(fc.args) if fc.args else {}, sort_keys=True)}"
                    futures[call_key] = (fc, pool.submit(
                        _execute_function_call, fc
                    ))

                for call_key, (fc, future) in futures.items():
                    timeout_sec = _get_tool_timeout(fc.name)  # timeout_policy 기반
                    llm_result_str = None
                    try:
                        result_str = future.result(timeout=timeout_sec)
                        status = "success"
                        if "[TIMEOUT]" in result_str or any(kw in result_str for kw in ["TIMEOUT", "응답 지연", "API 지연", "MCP_TIMEOUT"]):
                            status = "timeout"
                        elif any(kw in result_str for kw in ["[FAILED]", "MCP 호출 오류"]):
                            status = "failed"
                        elapsed_tool = int((time.time() - tool_start) * 1000)
                        llm_result_str, evidence_card, response_context_meta = _build_llm_tool_response(fc, result_str)
                        tool_result_entry = {
                            "tool_name": fc.name, "status": status,
                            "result": result_str, "elapsed_ms": elapsed_tool,
                            "tool_args": _function_args_dict(fc),
                            "raw_result_chars": len(result_str or ""),
                            "llm_result_chars": len(llm_result_str or ""),
                        }
                        if evidence_card:
                            tool_result_entry["evidence_card"] = evidence_card
                        tool_result_entry.update(response_context_meta)
                        all_tool_results.append(tool_result_entry)
                    except Exception as e:
                        elapsed_tool = int((time.time() - tool_start) * 1000)
                        result_str = json.dumps({"error": str(e)}, ensure_ascii=False)
                        llm_result_str, evidence_card, response_context_meta = _build_llm_tool_response(fc, result_str)
                        tool_result_entry = {
                            "tool_name": fc.name,
                            "status": "timeout" if "timeout" in str(e).lower() else "failed",
                            "result": result_str,
                            "elapsed_ms": elapsed_tool,
                            "tool_args": _function_args_dict(fc),
                            "raw_result_chars": len(result_str or ""),
                            "llm_result_chars": len(llm_result_str or ""),
                        }
                        if evidence_card:
                            tool_result_entry["evidence_card"] = evidence_card
                        tool_result_entry.update(response_context_meta)
                        all_tool_results.append({
                            **tool_result_entry,
                        })
                    response_parts.append(
                        types.Part.from_function_response(
                            name=fc.name,
                            response={"result": llm_result_str if llm_result_str is not None else result_str}
                        )
                    )

            contents.append(types.Content(role="user", parts=response_parts))
            current_contents_chars = _content_text_chars(contents)
            _current_llm_payload_meta["llm_payload_after_tool_response_chars"] = current_contents_chars
            _current_llm_payload_meta["llm_payload_max_contents_chars"] = max(
                int(_current_llm_payload_meta.get("llm_payload_max_contents_chars", 0) or 0),
                current_contents_chars,
            )
            
            # [NEW] 조기 탈출 (Fast-track) for low-risk company search
            is_company_tool_called = any(r["tool_name"] in company_tools + shopping_tools for r in all_tool_results)
            if risk_info.get("risk_level") == "low" and is_company_tool_called:
                print("  [FAST-TRACK] Low-risk company search executed. Skipping further reasoning/generation.", flush=True)
                fast_track_msg = "⚠️ 시스템은 현재 주어진 조건에 대해 단정적인 계약 가능 여부를 판단하지 않습니다. 판단 및 계약 진행 전 우선 관련 법령 및 수의계약 가능 여부를 체계적으로 검토하시기 바랍니다."
                
                answer, history = _finalize_answer(fast_track_msg, history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
                    "model_used": model_to_use,
                    "fallback_used": fallback_used,
                    "fallback_reason": fallback_reason,
                    "retry_count": total_retries,
                    "risk_level": risk_info.get("risk_level", "unknown"),
                    "high_risk_triggers": risk_info.get("high_risk_triggers", []),
                    "model_decision_reason": risk_info.get("model_decision_reason", ""),
                    "malformed_function_call_detected": malformed_function_call_detected,
                    "function_call_retry_count": function_call_retry_count,
                    "function_call_final_status": "success",
                    "fast_track_applied": True,
                    "deterministic_template_used": True,
                    "company_table_allowed": "company_search" in guardrails if 'guardrails' in locals() else False,
                    "core_prompt_hash": assembled.core_prompt_hash if 'assembled' in locals() and getattr(assembled, 'core_prompt_hash', '') else __import__('hashlib').sha256(b"deterministic_fast_track_fallback_core").hexdigest(),
                    "prompt_prefix_hash": assembled.prompt_prefix_hash if 'assembled' in locals() and getattr(assembled, 'prompt_prefix_hash', '') else __import__('hashlib').sha256(b"deterministic_fast_track_fallback_prefix").hexdigest()[:16],
                })
                return answer, history
            
            # 조기 탈출 (fail-closed)
            if any(r["status"] in ["timeout", "failed"] for r in all_tool_results):
                fail_to_cache = os.getenv("MCP_FAIL_TO_CACHE", "false").lower() == "true"
                if fail_to_cache:
                    print("  [FAIL_TO_CACHE] Timeout detected during LLM loop. Falling back to deterministic template.")
                    answer, history = _finalize_answer("", history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
                        "model_used": "bypass_timeout_fallback",
                        "tier_resolved": query_tier,
                        "mandatory_mcp_plan": mandatory_mcp_plan,
                        "mandatory_mcp_executed": mandatory_mcp_executed,
                        "mandatory_mcp_missing": mandatory_mcp_missing,
                        "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
                        "rag_elapsed_ms": rag_elapsed_ms if 'rag_elapsed_ms' in locals() else 0,
                        "model_elapsed_ms": 0,
                        "tool_call_count": len(all_tool_results),
                        "legal_basis_cache_used": True,
                        "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0) if 'cache_stats' in locals() else 0,
                        "source_status": "cached_stale_but_available" if cache_stats.get("legal_basis_cache_hit_count", 0) > 0 else "mcp_failed_no_basis",
                    })
                    return answer, history
                else:
                    print("  [EARLY EXIT] Timeout or failure detected, triggering fail-closed response.")
                    fallback_answer = "⚠️ API 연동 지연 또는 시스템 오류로 인해 검색이 중단되었습니다. 잠시 후 다시 시도해 주시거나 질문을 구체화해 주세요."
                    answer, history = _finalize_answer(fallback_answer, history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
                        "model_used": model_to_use,
                        "fallback_used": fallback_used,
                        "fallback_reason": fallback_reason,
                        "retry_count": total_retries - 1 if total_retries > 0 else 0,
                        "risk_level": risk_info.get("risk_level", "unknown"),
                        "high_risk_triggers": risk_info.get("high_risk_triggers", []),
                        "malformed_function_call_detected": malformed_function_call_detected,
                        "function_call_retry_count": function_call_retry_count,
                        "function_call_final_status": function_call_final_status,
                        "prefetch_tool_called": product_prefetch_executed if 'product_prefetch_executed' in locals() else False,
                        "prefetch_tool_name": forced_tool_name if 'product_prefetch_executed' in locals() and product_prefetch_executed else None,
                        "model_function_call_malformed": malformed_function_call_detected
                    })
                    return answer, history
        else:
            # Function call 없음 → 최종 답변

            preflight_evidence_available = bool(
                mandatory_mcp_executed
                or (evidence_cards if 'evidence_cards' in locals() else [])
                or (mcp_context if 'mcp_context' in locals() else "")
            )

            # 승인 조건 4: MCP required인데 tool call 없으면.
            # 단, 이미 내부 DB preflight 근거가 있으면 같은 질문을 chain_full_research로
            # 다시 태우지 않는다. 그 경우 Gemini는 카드/근거 기반 작성자로 끝낸다.
            if (
                intent_result.mcp_required
                and not mcp_was_called
                and round_i == 0
                and not tool_loop_gate_writer_only_enforced
                and LLM_TOOL_LOOP_ENABLED
                and not preflight_evidence_available
            ):
                print("  [PREFETCH] MCP required but no tool call")
                print("  [PREFETCH] forcing chain_full_research")
                start_prefetch = time.time()
                try:
                    # Legacy static check: prefetch_result = mcp.chain_full_research(...)
                    prefetch_call = call_mcp_with_timeout(
                        lambda query: mcp.chain_full_research(query),
                        "chain_full_research",
                        query=user_message,
                    )
                    prefetch_result = prefetch_call.get("result", "")
                    elapsed = prefetch_call.get("elapsed_ms", int((time.time() - start_prefetch) * 1000))
                    class _PrefetchFC:
                        name = "chain_full_research"
                        args = {"query": user_message}
                    prefetch_llm_result, prefetch_evidence_card, prefetch_context_meta = _build_llm_tool_response(
                        _PrefetchFC(),
                        prefetch_result,
                        selected_reason="forced_prefetch",
                    )
                    status = prefetch_call.get("status", "success")
                    if "[TIMEOUT]" in prefetch_result or any(kw in prefetch_result for kw in ["TIMEOUT", "응답 지연", "API 지연", "MCP_TIMEOUT"]):
                        status = "timeout"
                    elif any(kw in prefetch_result for kw in ["[FAILED]", "MCP 호출 오류"]):
                        status = "failed"
                    prefetch_entry = {
                        "tool_name": "chain_full_research", "status": status,
                        "result": prefetch_result, "elapsed_ms": elapsed,
                        "tool_args": {"query": user_message},
                        "raw_result_chars": len(prefetch_result or ""),
                        "llm_result_chars": len(prefetch_llm_result or ""),
                    }
                    if prefetch_evidence_card:
                        prefetch_entry["evidence_card"] = prefetch_evidence_card
                    prefetch_entry.update(prefetch_context_meta)
                    all_tool_results.append(prefetch_entry)
                    mcp_was_called = True
                    
                    if status in ["timeout", "failed"]:
                        fail_to_cache = os.getenv("MCP_FAIL_TO_CACHE", "false").lower() == "true"
                        if fail_to_cache:
                            print("  [FAIL_TO_CACHE] Prefetch timeout detected, falling back to deterministic template.")
                            answer, history = _finalize_answer("", history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
                                "model_used": "bypass_timeout_fallback",
                                "tier_resolved": query_tier,
                                "mandatory_mcp_plan": mandatory_mcp_plan,
                                "mandatory_mcp_executed": mandatory_mcp_executed,
                                "mandatory_mcp_missing": mandatory_mcp_missing,
                                "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
                                "rag_elapsed_ms": rag_elapsed_ms if 'rag_elapsed_ms' in locals() else 0,
                                "model_elapsed_ms": 0,
                                "tool_call_count": len(all_tool_results),
                                "legal_basis_cache_used": True,
                                "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0) if 'cache_stats' in locals() else 0,
                                "source_status": "cached_stale_but_available" if cache_stats.get("legal_basis_cache_hit_count", 0) > 0 else "mcp_failed_no_basis",
                            })
                            return answer, history
                        else:
                            print("  [EARLY EXIT] Prefetch failed, triggering fail-closed response.")
                            fallback_answer = "⚠️ 법령 검색 지연 또는 오류로 인해 답변이 유보되었습니다. 잠시 후 다시 시도해 주세요."
                            answer, history = _finalize_answer(fallback_answer, history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
                                "model_used": model_to_use,
                                "fallback_used": fallback_used,
                                "fallback_reason": fallback_reason,
                                "retry_count": total_retries - 1 if total_retries > 0 else 0,
                                "core_prompt_hash": assembled.core_prompt_hash if 'assembled' in locals() else "",
                                "prompt_prefix_hash": assembled.prompt_prefix_hash if 'assembled' in locals() else "",
                                "company_table_allowed": "company_search" in guardrails if 'guardrails' in locals() else False,
                                "tier_resolved": query_tier,
                                "mandatory_mcp_plan": mandatory_mcp_plan,
                                "mandatory_mcp_executed": mandatory_mcp_executed,
                                "mandatory_mcp_missing": mandatory_mcp_missing,
                                "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
                            "legal_basis_cache_used": cache_stats.get("legal_basis_cache_used", False) if 'cache_stats' in locals() else False,
                            "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0) if 'cache_stats' in locals() else 0,
                            "legal_basis_cache_miss_count": cache_stats.get("legal_basis_cache_miss_count", 0) if 'cache_stats' in locals() else 0,
                            "mcp_called_for_cache_miss": cache_stats.get("mcp_called_for_cache_miss", False) if 'cache_stats' in locals() else False,
                            "mcp_called_for_freshness": cache_stats.get("mcp_called_for_freshness", False) if 'cache_stats' in locals() else False,
                            "cache_status": cache_stats.get("cache_status", "") if 'cache_stats' in locals() else "",
                        })
                        return answer, history
                        
                    # Prefetch 결과를 대화에 추가하고 재시도
                    contents.append(types.Content(
                        role="user",
                        parts=[types.Part.from_text(
                            text=f"[MCP Prefetch 결과]\n{prefetch_llm_result}\n\n위 법령 조회 결과를 반영하여 최종 답변을 작성하세요."
                        )]
                    ))
                    current_contents_chars = _content_text_chars(contents)
                    _current_llm_payload_meta["llm_payload_after_forced_prefetch_chars"] = current_contents_chars
                    _current_llm_payload_meta["llm_payload_max_contents_chars"] = max(
                        int(_current_llm_payload_meta.get("llm_payload_max_contents_chars", 0) or 0),
                        current_contents_chars,
                    )
                    continue  # 다음 라운드에서 답변 생성
                except Exception as e:
                    print(f"  [PREFETCH] Failed: {e}")
                    all_tool_results.append({
                        "tool_name": "chain_full_research", "status": "failed",
                        "result": str(e), "elapsed_ms": 0,
                    })

            # --- 최종 답변 처리 (정상 종료) ---
            answer = candidate.content.parts[0].text if candidate.content.parts else ""
            answer, history = _finalize_answer(answer, history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
                "model_used": model_to_use,
                "fallback_used": fallback_used,
                "fallback_reason": fallback_reason,
                "retry_count": total_retries - 1 if total_retries > 0 else 0,
                "risk_level": risk_info.get("risk_level", "unknown"),
                "high_risk_triggers": risk_info.get("high_risk_triggers", []),
                "model_decision_reason": risk_info.get("model_decision_reason", ""),
                "malformed_function_call_detected": malformed_function_call_detected,
                "function_call_retry_count": function_call_retry_count,
                "function_call_final_status": function_call_final_status,
                "core_prompt_hash": assembled.core_prompt_hash if 'assembled' in locals() else "",
                "prompt_prefix_hash": assembled.prompt_prefix_hash if 'assembled' in locals() else "",
                "company_table_allowed": "company_search" in guardrails if 'guardrails' in locals() else False,
                "rag_elapsed_ms": rag_elapsed_ms if 'rag_elapsed_ms' in locals() else 0,
                "model_elapsed_ms": int((time.time() - model_start) * 1000) if 'model_start' in locals() else 0,
                "tool_call_count": len(all_tool_results),
                "tier_resolved": query_tier,
                "mandatory_mcp_plan": mandatory_mcp_plan,
                "mandatory_mcp_executed": mandatory_mcp_executed,
                "mandatory_mcp_missing": mandatory_mcp_missing,
                "evidence_cards": evidence_cards if 'evidence_cards' in locals() else [],
                "evidence_card_count": cache_stats.get("evidence_card_count", 0) if 'cache_stats' in locals() else 0,
                "internal_db_hit_count": cache_stats.get("internal_db_hit_count", 0) if 'cache_stats' in locals() else 0,
                "external_mcp_fallback_count": cache_stats.get("external_mcp_fallback_count", 0) if 'cache_stats' in locals() else 0,
                "evidence_missing_count": cache_stats.get("evidence_missing_count", 0) if 'cache_stats' in locals() else 0,
                "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
                "legal_basis_cache_used": cache_stats.get("legal_basis_cache_used", False) if 'cache_stats' in locals() else False,
                "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0) if 'cache_stats' in locals() else 0,
                "legal_basis_cache_miss_count": cache_stats.get("legal_basis_cache_miss_count", 0) if 'cache_stats' in locals() else 0,
                "mcp_called_for_cache_miss": cache_stats.get("mcp_called_for_cache_miss", False) if 'cache_stats' in locals() else False,
                "mcp_called_for_freshness": cache_stats.get("mcp_called_for_freshness", False) if 'cache_stats' in locals() else False,
                "cache_status": cache_stats.get("cache_status", "") if 'cache_stats' in locals() else "",
            })
            return answer, history

    # --- Loop exhausted (반복 한도 초과) ---
    print(f"  [WARNING] v1.4.4 loop exhausted after {MAX_TOOL_CALL_ROUNDS} rounds")
    fallback_answer = "⚠️ 법령·도구 조회 제한으로 확인이 필요하여 답변이 유보되었습니다. 질문을 더 구체적으로 입력해 주시거나 관리자에게 문의해 주세요."
    # api_status에 timeout 또는 failed가 없더라도, 강제로 fail-closed 처리하기 위해 가상의 timeout 에러를 주입
    if not any(r["status"] in ["timeout", "failed"] for r in all_tool_results):
        all_tool_results.append({
            "tool_name": "loop_exhausted_fallback", "status": "timeout",
            "result": "[TIMEOUT] 검색 반복 한도 초과", "elapsed_ms": 0,
        })
    answer, history = _finalize_answer(fallback_answer, history, user_message, all_tool_results, api_status, progress_callback, generation_meta={
        "model_used": model_to_use,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "retry_count": total_retries - 1 if total_retries > 0 else 0,
        "deterministic_template_used": True,
        "risk_level": risk_info.get("risk_level", "unknown"),
        "high_risk_triggers": risk_info.get("high_risk_triggers", []),
        "model_decision_reason": risk_info.get("model_decision_reason", ""),
        "malformed_function_call_detected": malformed_function_call_detected,
        "function_call_retry_count": function_call_retry_count,
        "function_call_final_status": function_call_final_status,
        "core_prompt_hash": assembled.core_prompt_hash if 'assembled' in locals() else "",
        "prompt_prefix_hash": assembled.prompt_prefix_hash if 'assembled' in locals() else "",
        "company_table_allowed": "company_search" in guardrails if 'guardrails' in locals() else False,
        "rag_elapsed_ms": rag_elapsed_ms if 'rag_elapsed_ms' in locals() else 0,
        "model_elapsed_ms": int((time.time() - model_start) * 1000) if 'model_start' in locals() else 0,
        "tool_call_count": len(all_tool_results),
        "tier_resolved": query_tier,
        "mandatory_mcp_plan": mandatory_mcp_plan,
        "mandatory_mcp_executed": mandatory_mcp_executed,
        "mandatory_mcp_missing": mandatory_mcp_missing,
        "mcp_preflight_elapsed_ms": mcp_preflight_elapsed_ms,
        "legal_basis_cache_used": cache_stats.get("legal_basis_cache_used", False) if 'cache_stats' in locals() else False,
        "legal_basis_cache_hit_count": cache_stats.get("legal_basis_cache_hit_count", 0) if 'cache_stats' in locals() else 0,
        "legal_basis_cache_miss_count": cache_stats.get("legal_basis_cache_miss_count", 0) if 'cache_stats' in locals() else 0,
        "mcp_called_for_cache_miss": cache_stats.get("mcp_called_for_cache_miss", False) if 'cache_stats' in locals() else False,
        "mcp_called_for_freshness": cache_stats.get("mcp_called_for_freshness", False) if 'cache_stats' in locals() else False,
        "cache_status": cache_stats.get("cache_status", "") if 'cache_stats' in locals() else "",
        "legacy_gemini_intent_router": legacy_router_meta if 'legacy_router_meta' in locals() else {"status": "not_available"},
    })
    return answer, history

def _finalize_answer(answer: str, history: list, user_message: str, all_tool_results: list, api_status: ApiStatus, progress_callback=None, generation_meta: dict = None):
    global _last_generation_meta, _current_evidence_context_meta, _current_llm_payload_meta
    _rewrite_start = time.time()
    
    if generation_meta is not None:
        for _k, _v in (_current_evidence_context_meta or {}).items():
            generation_meta.setdefault(_k, _v)
        for _k, _v in (_current_llm_payload_meta or {}).items():
            generation_meta.setdefault(_k, _v)
        for _k, _v in _summarize_tool_response_context(all_tool_results).items():
            generation_meta.setdefault(_k, _v)
        for _k, _v in (_current_intent_rag_meta or {}).items():
            generation_meta.setdefault(_k, _v)
        for _k, _v in (_current_routing_confidence_meta or {}).items():
            generation_meta.setdefault(_k, _v)
        for _k, _v in (_current_tool_loop_gate_meta or {}).items():
            generation_meta.setdefault(_k, _v)
        # deterministic_template_used가 이미 True이면 source를 deterministic으로 초기화
        if generation_meta.get("deterministic_template_used", False):
            generation_meta["final_answer_source"] = "deterministic_fail_closed_template"
        else:
            generation_meta["final_answer_source"] = "model_generation"
        # 라우팅 메타데이터 주입 (risk_info가 있으면)
        generation_meta.setdefault("model_routing_mode", os.getenv("MODEL_ROUTING_MODE", "risk_based"))
        generation_meta.setdefault("model_primary", os.getenv("GEMINI_MODEL", "gemini-2.5-pro"))
        generation_meta.setdefault("risk_level", "unknown")
        generation_meta.setdefault("high_risk_triggers", [])
        generation_meta.setdefault("direct_legal_basis_count", 0)
        
        # Schema Version 지정
        tier_resolved = generation_meta.get("tier_resolved", 1)
        if tier_resolved == 0:
            generation_meta["answer_schema_version"] = "simplified_company_search_v1"
        elif tier_resolved == 1:
            generation_meta["answer_schema_version"] = "amount_contract_guidance_v1"
        elif tier_resolved == 2:
            generation_meta["answer_schema_version"] = "regional_procurement_v2"
        elif tier_resolved == 3:
            generation_meta["answer_schema_version"] = "agency_specific_legal_review_v1"

    amount_detected = _parse_amount(user_message)
    if generation_meta is not None:
        generation_meta["amount_detected"] = amount_detected
    
    # LegalConclusionScope 계산
    legal_scope = evaluate_legal_scope(all_tool_results, user_message)
    api_status.legal_scope = legal_scope
    
    if generation_meta is not None:
        if generation_meta.get("malformed_function_call_detected", False):
            if "malformed_function_call" not in legal_scope.blocked_scope:
                legal_scope.blocked_scope.append("malformed_function_call")

        generation_meta["blocked_scope"] = legal_scope.blocked_scope
        generation_meta["legal_conclusion_allowed"] = legal_scope.legal_conclusion_allowed
    
    if not all_tool_results:
        api_status.mcp_status = "not_called"
    elif all(r["status"] == "success" for r in all_tool_results):
        api_status.mcp_status = "success"
    elif any(r["status"] == "success" for r in all_tool_results):
        api_status.mcp_status = "partial"
    elif any(r["status"] == "timeout" for r in all_tool_results):
        api_status.mcp_status = "timeout"
    else:
        api_status.mcp_status = "failed"

    # 회사 검색 상태(company_search_status) 수집
    company_results = [r for r in all_tool_results if "search_local_company" in r["tool_name"] or "search_shopping_mall" in r["tool_name"]]
    if company_results:
        is_empty_result = all("결과가 없습니다" in str(r.get("result", "")) or str(r.get("result", "")).strip() == "" for r in company_results)
        
        if is_empty_result:
            api_status.company_search_status = "no_results"
        elif all(r["status"] == "success" for r in company_results):
            api_status.company_search_status = "success"
        elif any(r["status"] == "success" for r in company_results):
            api_status.company_search_status = "partial"
        elif any(r["status"] == "timeout" for r in company_results):
            api_status.company_search_status = "timeout"
        else:
            api_status.company_search_status = "failed"

    # User requested: timeout or failed should force legal_conclusion_allowed to False
    if api_status.mcp_status in ["timeout", "failed"] or api_status.company_search_status in ["timeout", "failed"]:
        legal_scope.legal_conclusion_allowed = False
        # malformed이 이미 있으면 api_timeout 추가 안 함
        has_malformed = "malformed_function_call" in legal_scope.blocked_scope
        has_api_timeout = "api_timeout" in legal_scope.blocked_scope
        if not has_malformed and not has_api_timeout:
            # malformed mock에서 주입된 경우를 확인
            is_malformed_origin = any(
                "malformed" in str(r.get("result", "")).lower() or 
                "malformed" in str(r.get("status", "")).lower()
                for r in all_tool_results
            )
            if is_malformed_origin:
                legal_scope.blocked_scope.append("malformed_function_call")
                legal_scope.critical_missing.append("malformed_function_call")
            else:
                legal_scope.blocked_scope.append("api_timeout")
                legal_scope.critical_missing.append("api_timeout")

    # 승인 조건 3: verify_and_annotate
    if progress_callback:
        progress_callback("✅ 법령 인용 검증 중...")
    
    # fallback_answer인 경우 verify를 패스해도 됨
    skip_citation_verify = bool(generation_meta and generation_meta.get("skip_citation_verify", False))
    if "반복 한도 초과하여 답변이 유보되었습니다" not in answer and not skip_citation_verify:
        answer = _verify_and_annotate_v144(answer, all_tool_results)

    # 승인 조건 4: blocked_scope를 최종 답변에 실제 반영
    import re
    FORBIDDEN_CONFIRM_PATTERNS = [
        r"수의계약\s*(이\s*)?가능합니다",
        r"1인\s*견적\s*(이\s*)?가능합니다",
        r"계약\s*(이\s*)?가능합니다",
        r"구매\s*(가\s*)?가능합니다",
        r"가능한\s*것으로\s*판단됩니다",
        r"진행\s*가능합니다",
        r"불가능합니다",
        r"여성기업이므로\s*수의계약\s*가능합니다",
        r"바로\s*가능합니다",
        r"금액\s*제한\s*없이\s*(가능|진행)"
    ]
    matched_patterns = []
    for pattern in FORBIDDEN_CONFIRM_PATTERNS:
        if re.search(pattern, answer):
            matched_patterns.append(pattern)
            
    has_forbidden = len(matched_patterns) > 0
    if has_forbidden:
        legal_scope.legal_conclusion_allowed = False
        if "forbidden_confirmation_detected" not in legal_scope.blocked_scope:
            legal_scope.blocked_scope.append("forbidden_confirmation_detected")

    if generation_meta is not None:
        generation_meta["initial_forbidden_matched"] = matched_patterns
        generation_meta["has_forbidden_initial"] = has_forbidden

    LAW_ALIASES = {
        "지방자치단체를 당사자로 하는 계약에 관한 법률": "지방계약법",
        "조달사업에 관한 법률": "조달사업법",
        "국가를 당사자로 하는 계약에 관한 법률": "국가계약법",
        "중소기업제품 구매촉진 및 판로지원에 관한 법률": "판로지원법"
    }
    INCOMPLETE_LAWS = ["법", "시행령", "시행규칙", "특별법", "회계규칙", "시행세칙", "와 같은 법 시행령", "같은 법 시행령"]
    EXCLUDED_LAWS = ["부가가치세법", "조세특례제한법", "주거환경정비법", "수도법", "관세법", "중등학교 회계규칙", "강원특별자치도 관련 특별법"]

    legal_basis = []
    direct_basis_count = 0
    for r in all_tool_results:
        if r["status"] == "success" and r["tool_name"] in ["search_law", "get_law_text", "chain_full_research", "chain_action_basis"]:
            text = r["result"]
            law_pattern = r'([가-힣\s]+(?:법|령|규칙|기준|규정|조례)(?:\s*시행[령규칙])?)\s*(제\d+조(?:의\d+)?(?:(?:의\d+)*))(?:\s*(제\d+항))?(?:\s*(제\d+호))?'
            for m in re.finditer(law_pattern, text):
                raw_law_name = m.group(1).strip()
                article = m.group(2) if m.group(2) else ""
                paragraph = m.group(3) if m.group(3) else ""
                item = m.group(4) if m.group(4) else ""
                
                # Alias mapping
                law_name = raw_law_name
                law_alias = raw_law_name
                for full_name, alias in LAW_ALIASES.items():
                    if full_name in law_name:
                        law_alias = law_name.replace(full_name, alias)
                        break

                # Relevance and supports_claims
                relevance = "indirect"
                supports_claims = []
                
                # supports_claims 판단 (tool result 텍스트 기반, 그리고 최종 답변에 반영되었는지)
                context_snippet = text[max(0, m.start()-50):min(len(text), m.end()+150)]
                amount_pattern = r'(\d+[천만억백십]+원)'
                
                if re.search(amount_pattern, context_snippet) and re.search(amount_pattern, answer):
                    supports_claims.append("금액 한도")
                if "수의계약" in context_snippet and "수의계약" in answer:
                    supports_claims.append("수의계약 가능 여부")
                if "1인 견적" in context_snippet and "1인 견적" in answer:
                    supports_claims.append("1인 견적")
                if "여성기업" in context_snippet and "여성기업" in answer:
                    supports_claims.append("수의계약 대상 여부")
                if (
                    any(term in context_snippet for term in ("분리발주", "분리하여 도급", "도급의 분리"))
                    and any(term in answer for term in ("분리발주", "분리하여 도급", "분리하여 도급하는", "분리 도급", "도급하는 것이 원칙"))
                ):
                    supports_claims.append("분리발주 여부")
                if "기술성" in context_snippet and "기술성" in answer:
                    supports_claims.append("소프트웨어 기술성 평가")

                amount_values = []
                for m_ans in re.finditer(amount_pattern, answer):
                    ans_amt = m_ans.group(1)
                    if ans_amt in context_snippet:
                        amount_values.append(ans_amt)
                        if "금액 한도" not in supports_claims:
                            supports_claims.append("금액 한도")

                base_law_only = law_name.replace(" 시행령", "").replace(" 시행규칙", "").strip()
                
                if any(ex in law_name for ex in EXCLUDED_LAWS):
                    relevance = "excluded"
                    # 질문의 핵심이면 예외 처리
                    if any(ex in user_message for ex in EXCLUDED_LAWS if ex in law_name):
                        relevance = "direct" if supports_claims else "indirect"
                elif law_name in INCOMPLETE_LAWS:
                    relevance = "indirect"
                else:
                    if len(supports_claims) > 0:
                        relevance = "direct"
                    else:
                        relevance = "indirect"

                if relevance == "direct":
                    direct_basis_count += 1

                legal_basis.append({
                    "law_name": law_name,
                    "law_alias": law_alias,
                    "article": article,
                    "paragraph": paragraph,
                    "item": item,
                    "summary": context_snippet.strip()[:100],
                    "source_status": "confirmed",
                    "relevance": relevance,
                    "supports_claims": supports_claims,
                    "amount_value": amount_values[0] if amount_values else None
                })
                
    if generation_meta is not None:
        generation_meta["legal_basis"] = legal_basis

    preflight_grounded_fallback = bool(
        generation_meta
        and generation_meta.get("preflight_grounded_fallback")
        and int(generation_meta.get("direct_legal_basis_count", 0) or 0) > 0
    )
    if preflight_grounded_fallback:
        direct_basis_count = max(direct_basis_count, int(generation_meta.get("direct_legal_basis_count", 0) or 0))

    # direct legal_basis가 없으면 법적 결론을 내릴 수 없음
    if direct_basis_count == 0:
        legal_scope.legal_conclusion_allowed = False
        if "no_direct_legal_basis" not in legal_scope.blocked_scope:
            legal_scope.blocked_scope.append("no_direct_legal_basis")

    # final_answer의 claim 추출 및 교차 검증 로직
    law_article_claims = []
    amount_threshold_claims = []
    sole_contract_claims = []
    one_person_quote_claims = []
    
    law_pattern_ans = r'([가-힣\s]+(?:법|령|규칙|기준|규정|조례)(?:\s*시행[령규칙])?)\s*(제\d+조(?:의\d+)?)'
    for m in re.finditer(law_pattern_ans, answer):
        raw_law_name = m.group(1).strip()
        article = m.group(2)
        
        # alias 변환
        claim_alias = raw_law_name
        for full_name, alias in LAW_ALIASES.items():
            if full_name in raw_law_name:
                claim_alias = raw_law_name.replace(full_name, alias)
                break
        law_article_claims.append((claim_alias, article))
        
    amount_pattern_ans = r'(\d+[천만억백십]+원)'
    for m in re.finditer(amount_pattern_ans, answer):
        amount_threshold_claims.append(m.group(1))
        
    if "수의계약" in answer and any(kw in answer for kw in ["가능", "할 수 있", "대상", "체결"]):
        sole_contract_claims.append(True)
        
    if "1인 견적" in answer and any(kw in answer for kw in ["가능", "할 수 있", "대상", "제출"]):
        one_person_quote_claims.append(True)

    amount_value_claims = list(set(amount_threshold_claims))
    claim_validation = {
        "law_article_claim": "not_applicable",
        "amount_threshold_claim": "not_applicable",
        "amount_value_claim": "not_applicable",
        "sole_contract_claim": "not_applicable",
        "one_person_quote_claim": "not_applicable"
    }

    # 각 claim별 지원 여부 검증
    unsupported_legal_conclusion = False

    if law_article_claims:
        all_supported = True
        for claim_law, claim_article in law_article_claims:
            supported = False
            for basis in legal_basis:
                if basis["relevance"] == "direct" and (basis["law_alias"] == claim_law or basis["law_name"] == claim_law) and basis["article"].startswith(claim_article):
                    supported = True
                    break
            if not supported:
                all_supported = False
                break
        claim_validation["law_article_claim"] = "pass" if all_supported else "fail"

    if amount_threshold_claims:
        supported = any("금액 한도" in basis["supports_claims"] and basis["relevance"] == "direct" for basis in legal_basis)
        claim_validation["amount_threshold_claim"] = "pass" if supported else "fail"
        
    if amount_value_claims:
        all_supported = True
        for claim_val in amount_value_claims:
            supported = False
            for basis in legal_basis:
                if basis["relevance"] == "direct" and basis.get("amount_value") == claim_val:
                    supported = True
                    break
            if not supported:
                all_supported = False
                break
        claim_validation["amount_value_claim"] = "pass" if all_supported else "fail"

    if sole_contract_claims:
        supported = any("수의계약 가능 여부" in basis["supports_claims"] and basis["relevance"] == "direct" for basis in legal_basis)
        claim_validation["sole_contract_claim"] = "pass" if supported else "fail"

    if one_person_quote_claims:
        supported = any("1인 견적" in basis["supports_claims"] and basis["relevance"] == "direct" for basis in legal_basis)
        claim_validation["one_person_quote_claim"] = "pass" if supported else "fail"

    # claim 중 하나라도 fail이면 unsupported_legal_conclusion = True
    if any(val == "fail" for val in claim_validation.values()):
        unsupported_legal_conclusion = True

    if preflight_grounded_fallback and not has_forbidden:
        unsupported_legal_conclusion = False
        legal_scope.legal_conclusion_allowed = True
        legal_scope.blocked_scope = [
            scope for scope in legal_scope.blocked_scope
            if scope not in ("no_direct_legal_basis", "unsupported_legal_conclusion")
        ]
        for key, value in list(claim_validation.items()):
            if value == "fail":
                claim_validation[key] = "preflight_grounded"

    if generation_meta is not None:
        generation_meta["claim_validation"] = claim_validation

    if unsupported_legal_conclusion:
        legal_scope.legal_conclusion_allowed = False
        if "unsupported_legal_conclusion" not in legal_scope.blocked_scope:
            legal_scope.blocked_scope.append("unsupported_legal_conclusion")
            
    # 이미 안전한 템플릿(Fallback)이고 금지어도 없으면 Rewrite 생략 (초고속 탈출)
    if "검토 구조 안내 템플릿" in answer or "확인 필요 사항" in answer or "검토 구조는 다음과 같습니다" in answer:
        if not has_forbidden and not unsupported_legal_conclusion:
            # API 상태 표시 추가 후 즉시 리턴
            status_display = api_status.to_display()
            if status_display:
                answer += f"\n\n{status_display}"
            history.append({"role": "user", "text": user_message})
            history.append({"role": "model", "text": answer})
            
            if generation_meta:
                # [Phase 2] 업체 검색 메타데이터 초기화
                if "company_source_status" not in generation_meta:
                    generation_meta["company_cache_used"] = False
                    generation_meta["company_cache_refreshed_at"] = None
                    generation_meta["company_cache_age_hours"] = None
                    generation_meta["company_source_status"] = "no_company_query"
                    generation_meta["company_source_status_user_label"] = "업체검색 불필요"
                    generation_meta["company_search_status"] = "not_called"
                    generation_meta["company_data_sources_used"] = []
                    generation_meta["company_cache_mode"] = "none"

                # [Phase 3 보완] 강제 상태 지정
                if not generation_meta.get("source_status"):
                    _tier = generation_meta.get("tier_resolved", 1)
                    if _tier == 0:
                        generation_meta["source_status"] = "no_mcp_required"
                    else:
                        generation_meta["source_status"] = "mcp_failed_no_basis"

                generation_meta["legal_conclusion_allowed"] = legal_scope.legal_conclusion_allowed
                generation_meta["blocked_scope"] = legal_scope.blocked_scope
                generation_meta["final_answer_scanned"] = True

                _last_generation_meta = dict(generation_meta)
            return answer, history

    MISSING_MSG_MAP = {
        "chain_full_research_timeout": "법령 통합 조회 지연",
        "forbidden_confirmation_detected": "금지어(단정적 표현) 감지",
        "no_direct_legal_basis": "직접적 법적 근거 부족",
        "unsupported_legal_conclusion": "근거 없는 법적 판단 생성",
        "high_risk_query": "현재 응답에서는 수의계약 가능 여부와 금액 기준을 확정하지 않습니다. 실제 계약 전 혁신제품 지정 상태, 혁신장터 등록 여부, 조달청 계약 여부, 수요기관 적용 법령 확인이 필요합니다."
    }

    if generation_meta and generation_meta.get("fallback_used", False):
        # Fallback 사용 시: 금지어가 발견되거나, legal_conclusion_allowed가 False인 경우 Deterministic Template 적용
        if has_forbidden or not legal_scope.legal_conclusion_allowed or unsupported_legal_conclusion:
            print("  [REWRITE] Flash fallback output needs constraint. Applying deterministic template.")
            if has_forbidden or unsupported_legal_conclusion or direct_basis_count == 0:
                print("  [REWRITE] Forbidden phrases or unsupported claims detected in Flash output. Discarding answer.")
                
                # Check for no_results and company_search_status
                company_search_status = getattr(api_status, 'company_search_status', "not_called")
                mcp_status_val = getattr(api_status, 'mcp_status', "not_called")
                
                # Rebuild safe template specifically for the rejection case
                safe_template = "⚠️ **확인 필요 사항**\n"
                if not legal_scope.legal_conclusion_allowed:
                    if mcp_status_val == "success":
                        safe_template += "- 법령 판단 유보 (근거 부족)\n"
                    else:
                        safe_template += "- API 조회 실패/지연으로 법적 판단이 제한되었습니다.\n"
                
                if "amount_threshold" in legal_scope.blocked_scope:
                    safe_template += "- 금액 한도는 법령 조회 지연으로 확정되지 않았습니다. 법제처 법령정보센터에서 최신 기준을 확인하세요.\n"
                if "one_person_quote" in legal_scope.blocked_scope:
                    safe_template += "- 1인 견적 가능 여부는 확인되지 않았습니다.\n"
                
                if company_search_status == "no_results":
                    kw = "해당"
                    if "LED" in user_message or "조명" in user_message: kw = "LED 조명"
                    elif "CCTV" in user_message: kw = "CCTV"
                    answer = f"현재 검색 결과에서는 부산 지역 {kw} 업체 후보가 확인되지 않았습니다. 다만 나라장터 종합쇼핑몰, 조달등록 업체, 품목명 변형 검색 등을 통해 추가 확인할 수 있습니다.\n\n"
                    answer += safe_template + "- 계약 전 조달등록·품목 적합성·수의계약 가능 여부 확인이 필요합니다."
                    if generation_meta is not None:
                        generation_meta["flash_answer_discarded"] = True
                        generation_meta["final_answer_source"] = "deterministic_no_results_template"
                        generation_meta["deterministic_template_used"] = True
                        generation_meta["flash_answer_used_in_final"] = False
                        generation_meta["legal_basis"] = []
                        if generation_meta.get("claim_validation"):
                            for k, v in generation_meta["claim_validation"].items():
                                if v == "fail":
                                    generation_meta["claim_validation"][k] = "blocked"
                elif "search_local_company" in str(all_tool_results) or "search_shopping_mall" in str(all_tool_results) or "search_innovation" in str(all_tool_results) or company_search_status == "success":
                    # 후보군 분류 및 표 생성 (공용 모듈 사용)
                    from policies.candidate_policy import classify_candidates, get_candidate_counts
                    from policies.candidate_formatter import format_candidate_tables

                    classified = classify_candidates(all_tool_results, user_message)
                    counts = get_candidate_counts(classified)
                    route_candidate_options = _route_candidate_display_options_for_answer(
                        user_message,
                        all_tool_results,
                        generation_meta,
                    )
                    formatted = format_candidate_tables(
                        classified,
                        user_message,
                        safe_template,
                        **route_candidate_options,
                    )

                    if formatted:
                        answer = formatted
                    else:
                        answer = "(검색 결과에서 유효한 업체 후보를 추출하지 못했습니다.)\n\n"
                        answer += safe_template + "- 계약 전 조달등록·품목 적합성·수의계약 가능 여부 확인이 필요합니다."

                    if generation_meta is not None:
                        generation_meta["flash_answer_discarded"] = True
                        generation_meta["final_answer_source"] = "company_table_plus_deterministic_caution"
                        generation_meta["deterministic_template_used"] = True
                        generation_meta["flash_answer_used_in_final"] = False
                        has_any = any(v > 0 for v in counts.values())
                        if has_any:
                            generation_meta["company_table_preserved"] = True
                            generation_meta["safe_table_extracted"] = True
                        generation_meta.update(counts)
                        generation_meta["legal_basis"] = []
                        if generation_meta.get("claim_validation"):
                            for k, v in generation_meta["claim_validation"].items():
                                if v == "fail":
                                    generation_meta["claim_validation"][k] = "blocked"
                else:
                    answer = safe_template + "- 질문하신 조건에 대한 수의계약 가능 여부를 단정할 수 없으니, 실제 계약 전 관련 법령을 직접 확인하시기 바랍니다."
                    if generation_meta is not None:
                        generation_meta["flash_answer_discarded"] = True
                        generation_meta["final_answer_source"] = "deterministic_fail_closed_template"
                        generation_meta["deterministic_template_used"] = True
                        generation_meta["flash_answer_used_in_final"] = False
                        generation_meta["legal_basis"] = []
                        if generation_meta.get("claim_validation"):
                            for k, v in generation_meta["claim_validation"].items():
                                if v == "fail":
                                    generation_meta["claim_validation"][k] = "blocked"
            else:
                answer += f"\n\n---\n{safe_template}"
                if generation_meta is not None:
                    generation_meta["flash_answer_discarded"] = False
                    # deterministic_template_used가 이미 True이면 final_answer_source를 보존
                    if not generation_meta.get("deterministic_template_used", False):
                        generation_meta["final_answer_source"] = "model_generation_with_caution"
                    generation_meta["flash_answer_used_in_final"] = False if not legal_scope.legal_conclusion_allowed else True
                    if not legal_scope.legal_conclusion_allowed:
                        generation_meta["legal_basis"] = []
        else:
            if generation_meta is not None:
                generation_meta["flash_answer_discarded"] = False
                generation_meta["final_answer_source"] = "model_generation"
                generation_meta["flash_answer_used_in_final"] = True
    else:
        # 승인 조건 4: blocked_scope를 최종 답변에 실제 반영 (Pro 정상)
        is_deterministic = generation_meta and generation_meta.get("deterministic_template_used", False)
        is_tier_0 = generation_meta and generation_meta.get("tier_resolved", 1) == 0
        is_amount_route = amount_detected is not None
        is_practice_manual_fast = generation_meta and (
            generation_meta.get("model_used") == "practice_manual_fast_gate"
            or generation_meta.get("source_status") == "practice_manual_cards"
        )
        
        final_answer_source = generation_meta.get("final_answer_source", "") if generation_meta else ""
        has_deterministic_source = "deterministic" in final_answer_source
        
        should_bypass_rewrite = (
            is_deterministic
            or is_tier_0
            or is_amount_route
            or has_deterministic_source
            or is_practice_manual_fast
        )
        
        if not legal_scope.legal_conclusion_allowed and not should_bypass_rewrite:
            rewrite_prompt = (
                f"다음은 사용자의 질문에 대한 초안 답변입니다:\n{answer}\n\n"
                "하지만 법령/API 조회가 실패하거나 지연되어 일부 판단이 제한되었습니다.\n"
                "초안 내용 중 '가능합니다', '불가합니다'와 같은 확정적 표현을 '관련 법령 확인이 필요합니다', '판단이 제한됩니다' 등의 유보적 표현으로 모두 수정하세요.\n"
                "답변 내용 하단에 다음의 경고 문구를 반드시 추가하세요:\n\n"
                "---\n⚠️ **확인 필요 사항**\n"
            )
            if "amount_threshold" in legal_scope.blocked_scope:
                rewrite_prompt += "- 금액 한도는 법령 조회 지연으로 확정되지 않았습니다. 법제처 법령정보센터에서 최신 기준을 확인하세요.\n"
            if "one_person_quote" in legal_scope.blocked_scope:
                rewrite_prompt += "- 1인 견적 가능 여부는 확인되지 않았습니다.\n"
            for item in legal_scope.critical_missing:
                if item != "api_timeout":
                    display_item = MISSING_MSG_MAP.get(item, item.replace('_', ' '))
                    rewrite_prompt += f"- {display_item}\n"
            
            rewrite_prompt += "\n**중요 지침:** '알겠습니다', '수정하겠습니다', '초안 답변을'과 같은 대화형 문구나 내부 처리 과정을 암시하는 문구를 절대 포함하지 마시고, 즉시 최종 사용자에게 보여줄 응답 본문 텍스트만 출력하세요."
                
            try:
                rewrite_model = generation_meta.get("model_used", MODEL_ID) if generation_meta else MODEL_ID
                if rewrite_model == "bypass_timeout_fallback":
                    rewrite_model = MODEL_ID
                    
                rewrite_response = client.models.generate_content(
                    model=rewrite_model,
                    contents=[types.Content(role="user", parts=[types.Part.from_text(text=rewrite_prompt)])],
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                        thinking_config=_thinking_config_for(GEMINI_REWRITE_THINKING_BUDGET),
                    )
                )
                answer = rewrite_response.text if rewrite_response.text else answer
            except Exception as e:
                print(f"  [WARNING] Rewrite failed: {e}")
                # Rewrite 실패 시 직접 추가
                answer += "\n\n---\n⚠️ **확인 필요 사항**\n- API 지연으로 일부 판단이 제한되었습니다."
            
            # Rewrite 후에도 남아있는 금지 표현 강제 치환 (Fail-safe)
            original_answer_before_rewrite = answer
            answer = re.sub(r"수의계약이?\s*가능(합니다|하며|할|해|하므로)", r"수의계약 검토가 가능\1", answer)
            answer = re.sub(r"1인\s*견적(?:이)?\s*가능(합니다|하며|할|해|하므로)", r"1인 견적 수의계약 검토가 가능\1", answer)
            answer = re.sub(r"금액\s*제한\s*없이", "관련 규정에 따라 금액 한도 예외 적용이 가능한지 확인 후", answer)
            answer = re.sub(r"금액\s*무제한", "규정에 따른 한도 예외", answer)
            answer = re.sub(r"계약\s*체결이?\s*가능합니다", "계약 검토가 가능합니다", answer)
            
            # 치환 후 카운트 비교
            if generation_meta is not None:
                # post_scan_patterns 미리 정의
                post_scan_patterns_list = [
                    r"수의계약 추진", r"수의계약을 추진", r"수의계약 체결", r"1인 견적 수의계약 체결",
                    r"1인 견적에 의한 수의계약", r"1인 견적 수의계약", r"금액과 상관없이", r"금액 제한 없이",
                    r"금액 한도 없이", r"금액 제한이 없더라도", r"직접 수의계약", r"계약을 추진",
                    r"계약 가능합니다", r"구매 가능합니다", r"해당 업체와 직접 계약", r"직접 계약",
                    r"수의계약을 진행할 수 있습니다", r"수의계약 가능합니다", r"수의계약으로 구매할 수",
                    r"수의계약 대상으로 명시", r"수의계약이 가능하다고", r"수의계약 가능하다고 알려져",
                    r"계약 방식.*수의계약", r"금액 제한이 없지만", r"금액에 관계없이 수의계약",
                    r"바로 계약", r"바로 구매", r"수의계약 진행을 검토", r"수의계약으로 진행",
                    r"수의계약 진행 가능", r"수의계약을 검토해 볼 수"
                ]
                
                # regex_rewrite_applied=True 이전에 어떤 패턴들이 탐지되었는지 기록
                before_forbidden = []
                for pat in post_scan_patterns_list:
                    if re.search(pat, original_answer_before_rewrite):
                        before_forbidden.append(pat)
                generation_meta["forbidden_patterns_detected_before_rewrite"] = before_forbidden
                
                # 정규식으로 치환된 대략적인 건수 측정 (원본 텍스트 길이 변경 여부 확인)
                if answer != original_answer_before_rewrite:
                    generation_meta["rewritten_sentences_count"] = 1 # 단순화하여 1로 기록
                else:
                    generation_meta["rewritten_sentences_count"] = 0
                
                # 치환 후 남은 금지 표현 다시 스캔 코드는 제거됨 (요청사항 반영)

                # deterministic_template_used가 이미 True이면 final_answer_source를 보존
                if not generation_meta.get("deterministic_template_used", False):
                    generation_meta["final_answer_source"] = "model_generation_with_caution"
                generation_meta["flash_answer_used_in_final"] = False
        else:
            if generation_meta is not None:
                # deterministic_template_used가 이미 True이면 final_answer_source를 보존
                if not generation_meta.get("deterministic_template_used", False):
                    generation_meta["final_answer_source"] = "model_generation"
                generation_meta["flash_answer_used_in_final"] = True

        # 3) 후보군 검색이 있었을 경우 표 생성
        company_search_status = getattr(api_status, 'company_search_status', 'not_called')
        server_table = ""
        formatted = ""
        classified_candidate_count = 0
        formatter_input_count = 0
        formatter_output_chars = 0
        if "search_local_company" in str(all_tool_results) or "search_shopping_mall" in str(all_tool_results) or "search_innovation" in str(all_tool_results) or "search_tech" in str(all_tool_results) or company_search_status == "success":
            from policies.candidate_policy import classify_candidates, get_candidate_counts
            from policies.candidate_formatter import format_candidate_tables

            all_tool_results = _filter_company_tool_results_by_item(
                all_tool_results,
                user_message,
                generation_meta,
            )

            # tool_results의 JSON result를 파싱하여 structured_rows를 상위 레벨로 병합
            enriched_results = []
            for tr in all_tool_results:
                enriched = dict(tr)
                result_str = tr.get("result", "")
                if isinstance(result_str, str) and result_str.startswith("{"):
                    try:
                        parsed = json.loads(result_str)
                        if isinstance(parsed, dict):
                            for k in ["structured_rows", "product_sample_rows"]:
                                if k in parsed and k not in enriched:
                                    enriched[k] = parsed[k]
                    except (json.JSONDecodeError, TypeError):
                        pass
                enriched_results.append(enriched)

            classified = classify_candidates(enriched_results, user_message)
            counts = get_candidate_counts(classified)
            classified_candidate_count = sum(len(v) for v in classified.values())
            formatter_input_count = classified_candidate_count
            
            # 스테이징 모드 환경변수가 1로 설정된 경우 is_staging=True로 전달
            is_staging = os.getenv("STAGING_MODE") == "1"
            route_candidate_options = _route_candidate_display_options_for_answer(
                user_message,
                enriched_results,
                generation_meta,
            )
            formatted = format_candidate_tables(
                classified,
                user_message,
                "",
                is_staging=is_staging,
                **route_candidate_options,
            )
            formatter_output_chars = len(formatted) if formatted else 0

            # counts를 generation_meta에 주입 (분기 내부에서만 정의됨)
            if generation_meta is not None:
                generation_meta.update(counts)  # local_company_count, mall_company_count 등

        if generation_meta is not None:
            generation_meta["classified_candidate_count"] = classified_candidate_count
            generation_meta["formatter_input_count"] = formatter_input_count
            generation_meta["formatter_output_chars"] = formatter_output_chars

    # 일부 빠른 경로는 업체 formatter 분기를 거치지 않으므로 기본값을 보장한다.
    server_table = locals().get("server_table", "")
    formatted = locals().get("formatted", "")
    classified_candidate_count = locals().get("classified_candidate_count", 0)
    formatter_input_count = locals().get("formatter_input_count", 0)
    formatter_output_chars = locals().get("formatter_output_chars", 0)

    # LLM 생성 업체/후보 표 감지 및 폐기
    # 법령ㆍ계약경로 비교표는 답변 품질 요소이므로 보존하고,
    # 업체DB 성격의 표만 서버 formatter 결과로 대체한다.
    _multi_route_prefetched = generation_meta.get("tier_resolved") == 2 if generation_meta else False
    _server_owned_markdown_table = bool(generation_meta and (
        generation_meta.get("deterministic_template_used", False)
        or generation_meta.get("model_used") in (
            "practice_manual_fast_gate",
            "intent_rag_pps_qa_fast_gate",
            "deterministic_internal_law_db",
        )
        or generation_meta.get("final_answer_source") in (
            "practice_manual_fast_answer",
            "intent_rag_pps_qa_fast_answer",
        )
    ))
    llm_has_table = bool(re.search(r"\|.*\|.*\n\|.*(?:---|-|:).*\|", answer))
    if llm_has_table and _server_owned_markdown_table:
        if generation_meta is not None:
            generation_meta["server_owned_markdown_table_preserved"] = True
            generation_meta["llm_generated_table_detected"] = False
            generation_meta["llm_generated_table_discarded"] = False
    elif llm_has_table and not _multi_route_prefetched:
        answer_without_candidate_tables, removed_table_count = _strip_candidate_or_company_markdown_tables(answer)
        if generation_meta is not None:
            generation_meta["llm_generated_table_detected"] = True
            generation_meta["llm_generated_candidate_table_removed_count"] = removed_table_count
            generation_meta["llm_generated_table_discarded"] = removed_table_count > 0

        if removed_table_count > 0:
            answer = answer_without_candidate_tables
            if formatted:
                server_table = formatted
                if "표" not in answer:
                    answer += f"\n\n---\n{server_table}"
                else:
                    answer += f"\n\n---\n**[시스템 자동 생성 표]**\n{server_table}"
        elif generation_meta is not None:
            generation_meta["llm_non_candidate_markdown_table_preserved"] = True

        if removed_table_count == 0 and formatted:
            server_table = formatted
            answer += f"\n\n---\n{server_table}"
    elif llm_has_table and _multi_route_prefetched:
        # 멀티 라우트: LLM의 구매경로 표는 보존하되, 업체 후보표는
        # 서버 formatter가 만든 구조화 표를 뒤에 붙인다.
        if formatted:
            server_table = formatted
            answer += f"\n\n---\n{server_table}"
        if generation_meta is not None:
            generation_meta["llm_generated_table_detected"] = True
            generation_meta["llm_generated_table_discarded"] = False
            generation_meta["candidate_table_source"] = (
                "llm_multi_route_plus_server_structured_formatter"
                if formatted else "llm_multi_route"
            )
            generation_meta["candidate_table_preserved"] = bool(formatted)
    elif formatted:
        # LLM이 표를 생성하지 않았지만 formatter 결과가 있으면 서버 표로 추가
        server_table = formatted
        if "[SERVER_TABLE_PLACEHOLDER]" in answer:
            answer = answer.replace("[SERVER_TABLE_PLACEHOLDER]", server_table)
        else:
            answer += f"\n\n---\n{server_table}"
        
        if generation_meta is not None and generation_meta.get("deterministic_template_used", False):
            generation_meta["final_answer_source"] = "deterministic_template_plus_server_table"

    # ==========================================
    # Post-Final Scanner (최종 안전 게이트)
    # ==========================================
    from policies.post_scan_policy import scan_final_answer
    post_scan_result = scan_final_answer(answer)
    post_scan_forbidden = list(post_scan_result.get("critical_patterns", []))
    post_scan_warnings = list(post_scan_result.get("warning_patterns", []))
    post_scan_patterns = post_scan_forbidden
    prompt_leak_detected = bool(post_scan_result.get("prompt_leak_detected", False))

    if generation_meta is not None:
        generation_meta["final_answer_scanned"] = True
        existing_forbidden = generation_meta.get("forbidden_patterns_matched", [])
        combined_forbidden = list(set(existing_forbidden + post_scan_forbidden))
        generation_meta["forbidden_patterns_matched"] = combined_forbidden
        generation_meta["post_scan_policy_version"] = post_scan_result.get("scanner_policy_version", "graded_v1")
        generation_meta["post_scan_findings"] = post_scan_result.get("findings", [])
        generation_meta["post_scan_critical_count"] = post_scan_result.get("critical_count", 0)
        generation_meta["post_scan_warning_count"] = post_scan_result.get("warning_count", 0)
        generation_meta["post_scan_warning_patterns"] = post_scan_warnings
        existing_candidate_source = generation_meta.get("candidate_table_source")
        if server_table:
            generation_meta["candidate_table_source"] = "server_structured_formatter"
        elif existing_candidate_source in ("llm_multi_route", "company_api_prefetch"):
            generation_meta["candidate_table_source"] = existing_candidate_source
        else:
            generation_meta["candidate_table_source"] = "none"
        generation_meta.setdefault("candidate_table_preserved", False)
        generation_meta.setdefault("llm_generated_table_discarded", False)
        generation_meta["prompt_leak_detected"] = prompt_leak_detected
        if "rewritten_sentences_count" not in generation_meta:
            generation_meta["rewritten_sentences_count"] = 0

    # ──────────────────────────────────────────────────────────
    # 금액 파싱 및 검토 경로 제공 로직
    # ──────────────────────────────────────────────────────────
    regional_pref = _detect_regional_preference(user_message)
    amount_band = None
    general_small_value_sole_quote = None
    policy_company_sole_quote = None

    if amount_detected is not None:
        try:
            from policies.numeric_basis_policy import get_numeric_value
            general_one_quote_limit = get_numeric_value("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
            policy_one_quote_limit = get_numeric_value("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD")
            two_quote_limit = get_numeric_value("P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD")
        except Exception:
            general_one_quote_limit = policy_one_quote_limit = two_quote_limit = None

        if isinstance(general_one_quote_limit, (int, float)) and amount_detected <= general_one_quote_limit:
            amount_band = "within_general_one_quote_threshold"
            general_small_value_sole_quote = "within_threshold"
            policy_company_sole_quote = "within_threshold"
        elif isinstance(policy_one_quote_limit, (int, float)) and amount_detected <= policy_one_quote_limit:
            amount_band = "above_general_within_policy_one_quote_threshold"
            general_small_value_sole_quote = "exceeds_threshold"
            policy_company_sole_quote = "within_threshold"
        elif isinstance(two_quote_limit, (int, float)) and amount_detected <= two_quote_limit:
            amount_band = "above_policy_one_quote_within_two_quote_threshold"
            general_small_value_sole_quote = "exceeds_threshold"
            policy_company_sole_quote = "exceeds_threshold"
        elif isinstance(two_quote_limit, (int, float)):
            amount_band = "above_two_quote_threshold"
            general_small_value_sole_quote = "exceeds_threshold"
            policy_company_sole_quote = "exceeds_threshold"
        else:
            amount_band = "threshold_unknown"

    # ── source_call_statuses 수집 ──
    source_call_statuses = {}
    for r in all_tool_results:
        tn = r.get("tool_name", "unknown")
        source_call_statuses[tn] = r.get("status", "unknown")

    # ── candidate_counts_by_type 수집 ──
    candidate_counts_by_type = {}
    if generation_meta is not None:
        candidate_counts_by_type = {
            "local_procurement_company": generation_meta.get("local_company_count", 0),
            "shopping_mall_supplier": generation_meta.get("mall_company_count", 0),
            "policy_company": generation_meta.get("tagged_policy_company_count", 0),
            "innovation_product": generation_meta.get("innovation_product_count", 0),
            "priority_purchase_product": generation_meta.get("priority_purchase_count", 0),
        }

    # ── Phase 2: 업체 데이터 캐시 상태 분리 ──
    if generation_meta is not None:
        if "company_source_status" not in generation_meta:
            generation_meta["company_cache_used"] = False
            generation_meta["company_cache_refreshed_at"] = None
            generation_meta["company_cache_age_hours"] = None
            generation_meta["company_source_status"] = "no_company_query"
            generation_meta["company_source_status_user_label"] = "업체검색 불필요"
            generation_meta["company_search_status"] = getattr(api_status, 'company_search_status', 'not_called')
            generation_meta["company_data_sources_used"] = []
            generation_meta["company_cache_mode"] = "none"

        used_sources = []
        is_live = False
        is_cached = False
        company_tool_used = False
        local_company_view_available = False
        try:
            local_company_view_available = bool(company_api.company_db.get_db_path())
        except Exception:
            local_company_view_available = False
        
        for tr in all_tool_results:
            tn = tr.get("tool_name", "")
            if (
                "search_company" in tn
                or "search_local_company" in tn
                or "search_shopping_mall" in tn
                or "search_certified_product" in tn
                or "search_innovation_product" in tn
                or "search_excellent_procurement_product" in tn
            ):
                used_sources.append(tn)
                company_tool_used = True
                if local_company_view_available:
                    is_cached = True
                else:
                    is_live = True
            elif "search_innovation" in tn or "search_tech" in tn:
                used_sources.append(tn)
                is_cached = True

        if company_tool_used or is_live or is_cached or generation_meta.get("company_search_status") not in ("not_called", None):
            if is_live and is_cached:
                generation_meta["company_source_status"] = "mixed_company_sources"
                generation_meta["company_source_status_user_label"] = "실시간 업체 조회와 로컬 캐시 혼합 사용"
                generation_meta["company_cache_mode"] = "hybrid"
                generation_meta["company_cache_used"] = True
            elif is_live:
                generation_meta["company_source_status"] = "live_company_lookup"
                generation_meta["company_source_status_user_label"] = "실시간 업체 데이터 조회 사용"
                generation_meta["company_cache_mode"] = "live_only"
                generation_meta["company_cache_used"] = False
            elif is_cached:
                generation_meta["company_source_status"] = "cached_daily"
                if local_company_view_available:
                    generation_meta["company_source_status_user_label"] = "내부 업체 DB VIEW 직접 조회"
                    generation_meta["company_cache_mode"] = "local_view_db"
                else:
                    generation_meta["company_source_status_user_label"] = "일 단위 갱신 업체 데이터 사용"
                    generation_meta["company_cache_mode"] = "daily_cache"
                generation_meta["company_cache_used"] = True
            
            # Remove duplicates while preserving order
            generation_meta["company_data_sources_used"] = list(dict.fromkeys(used_sources))


    # ── source_status 사전 결정 (builder가 참조할 수 있도록) ──
    # missing 우선순위로 처리
    if generation_meta is not None and ("source_status" not in generation_meta or not generation_meta["source_status"]):
        _pre_mcp = generation_meta.get("mandatory_mcp_executed", [])
        _pre_missing = generation_meta.get("mandatory_mcp_missing", [])
        _pre_tier = generation_meta.get("tier_resolved", 1)
        _pre_hits = generation_meta.get("legal_basis_cache_hit_count", 0)
        if _pre_tier == 0:
            generation_meta["source_status"] = "no_mcp_required"
        elif _pre_missing and _pre_mcp:
            generation_meta["source_status"] = "partial_mcp_with_missing"
        elif _pre_missing and _pre_hits > 0:
            generation_meta["source_status"] = "cached_stale_but_available"
        elif _pre_missing and not _pre_mcp and _pre_hits == 0:
            generation_meta["source_status"] = "mcp_failed_no_basis"
        elif _pre_hits > 0 and not _pre_missing:
            generation_meta["source_status"] = "cached_verified"
        elif _pre_mcp and generation_meta.get("mcp_called_for_cache_miss"):
            generation_meta["source_status"] = "cache_refreshed_from_mcp"
        elif _pre_mcp:
            generation_meta["source_status"] = "mcp_preflight_success"
        else:
            generation_meta["source_status"] = "mcp_failed_no_basis"

    amount_rewrite_bypass = bool(generation_meta and generation_meta.get("amount_rewrite_bypass", False))
    if post_scan_forbidden or prompt_leak_detected or (amount_detected is not None and not amount_rewrite_bypass):
        if amount_detected is not None:
            tier_resolved = generation_meta.get("tier_resolved", 1) if generation_meta else 1
            mcp_executed = generation_meta.get("mandatory_mcp_executed", []) if generation_meta else []

            # 멀티 라우트 사전검색(tier 2)인 경우 LLM 답변 보존
            if tier_resolved == 2 and _multi_route_prefetched:
                # LLM이 사전검색 데이터를 기반으로 구매 경로별 분석·그룹핑한 답변 유지
                if generation_meta is not None:
                    generation_meta["answer_discarded"] = False
                    generation_meta["deterministic_template_used"] = False
                    generation_meta["candidate_table_source"] = "llm_multi_route"
                    generation_meta["amount_detected"] = amount_detected
            else:
                from policies.answer_builder_policy import (
                    build_amount_contract_guidance_answer,
                    build_regional_procurement_answer
                )
                
                if tier_resolved == 2:
                    route_answer = build_regional_procurement_answer(generation_meta if generation_meta else {}, mcp_executed)
                else:
                    route_answer = build_amount_contract_guidance_answer(generation_meta if generation_meta else {}, mcp_executed)
                    
                answer = route_answer
                
                if server_table:
                    # Replace placeholder if exists, otherwise append
                    if "[SERVER_TABLE_PLACEHOLDER]" in answer:
                        answer = answer.replace("[SERVER_TABLE_PLACEHOLDER]", f"**[시스템 자동 추출 후보 표]**\n{server_table}")
                    else:
                        answer += f"\n\n**[시스템 자동 추출 후보 표]**\n{server_table}"
                else:
                    answer = answer.replace("[SERVER_TABLE_PLACEHOLDER]", "(검색 결과에서 유효한 업체 후보를 추출하지 못했습니다.)")

                if generation_meta is not None:
                    generation_meta["amount_detected"] = amount_detected
                    generation_meta["amount_band"] = amount_band
                    generation_meta["general_small_value_sole_quote"] = general_small_value_sole_quote
                    generation_meta["policy_company_sole_quote"] = policy_company_sole_quote
                    generation_meta["candidate_counts_by_type"] = candidate_counts_by_type
                    generation_meta["source_call_statuses"] = source_call_statuses
                    generation_meta["sensitive_fields_removed"] = True
                    generation_meta["enrichment_join_key_redacted"] = True
                    if server_table:
                        generation_meta["candidate_table_preserved"] = True
                    generation_meta["llm_generated_table_discarded"] = True
                    generation_meta["answer_discarded"] = True
                    generation_meta["deterministic_template_used"] = True
                    generation_meta["forbidden_patterns_matched"] = []
                    # Remove post scan forbidden since we replaced the answer entirely
                    post_scan_forbidden.clear()
        else:
            # LLM 법적 판단 문장 및 유출 문장 폐기 (Fail-closed 전환)
            if server_table:
                answer = "⚠️ 질문하신 조건에 대한 계약 가능 여부나 금액 한도는 시스템이 단정할 수 없습니다. 계약 전 관련 법령 및 지침을 직접 확인하시기 바랍니다.\n\n"
                answer += f"**[시스템 자동 추출 후보 표]**\n{server_table}"
                if generation_meta is not None:
                    generation_meta["candidate_table_preserved"] = True
                    generation_meta["final_answer_source"] = "deterministic_template_plus_server_table"
            else:
                answer = "⚠️ 질문하신 조건에 대한 계약 가능 여부나 금액 한도는 시스템이 단정할 수 없습니다. 계약 전 관련 법령 및 지침을 직접 확인하시기 바랍니다.\n\n"
                if generation_meta is not None:
                    generation_meta["final_answer_source"] = "deterministic_fail_closed_template"
                    
            if generation_meta is not None:
                generation_meta["llm_generated_table_discarded"] = True
                generation_meta["deterministic_template_used"] = True
                generation_meta["answer_discarded"] = True
                generation_meta["llm_legal_judgment_discarded"] = True
                generation_meta["regex_rewrite_applied"] = True
                generation_meta["forbidden_patterns_matched"] = []
                generation_meta["rewritten_sentences_count"] += len(post_scan_forbidden)
                generation_meta["source_call_statuses"] = source_call_statuses
                generation_meta["candidate_counts_by_type"] = candidate_counts_by_type
                generation_meta["sensitive_fields_removed"] = True
                generation_meta["enrichment_join_key_redacted"] = True

    # ── Phase 5: Raw tool name 은닉 (Safety Net) ──
    from policies.answer_builder_policy import strip_raw_tool_names
    answer = strip_raw_tool_names(answer)

    # 선택적 자연어 writer: 후보표/근거표는 서버 생성본을 보존하고 본문만 다듬는다.
    answer = _apply_natural_language_writer(answer, user_message, generation_meta)

    # API 상태 표시
    status_display = api_status.to_display()
    if status_display:
        answer += f"\n\n{status_display}"

    if generation_meta is not None:
        if "legal_basis" not in generation_meta:
            generation_meta["legal_basis"] = legal_basis
        # 안전 정책: legal_basis가 비어있으면 legal_conclusion_allowed 강제 False.
        # 단, v1.4.4 preflight가 내부 DB 근거를 이미 확보한 빠른 경로는
        # regex 기반 인용 추출이 실패해도 근거 자체는 존재하므로 보존한다.
        has_preflight_basis = bool(generation_meta.get("mandatory_mcp_executed"))
        if not legal_basis and legal_scope.legal_conclusion_allowed and not has_preflight_basis:
            legal_scope.legal_conclusion_allowed = False
            if not legal_scope.blocked_scope:
                legal_scope.blocked_scope = ["no_direct_legal_basis", "unsupported_legal_conclusion"]
            generation_meta["blocked_scope"] = legal_scope.blocked_scope
        generation_meta["legal_conclusion_allowed"] = legal_scope.legal_conclusion_allowed
        
        # 1. forbidden_patterns_remaining_after_rewrite: 최종 답변 기준 남은 금지 표현
        remaining_forbidden = []
        for pat in post_scan_patterns:
            if re.search(pat, answer):
                remaining_forbidden.append(pat)
        generation_meta["forbidden_patterns_remaining_after_rewrite"] = remaining_forbidden

        # rewrite elapsed 기록
        generation_meta["rewrite_elapsed_ms"] = int((time.time() - _rewrite_start) * 1000)

        # source_status 결정 로직
        if "source_status" not in generation_meta or not generation_meta["source_status"]:
            mcp_exec = generation_meta.get("mandatory_mcp_executed", [])
            tier = generation_meta.get("tier_resolved", 1)
            hit_count = generation_meta.get("legal_basis_cache_hit_count", 0)
            
            if tier == 0:
                generation_meta["source_status"] = "no_mcp_required"
            elif hit_count > 0:
                generation_meta["source_status"] = "cached_verified"
            elif mcp_exec:
                generation_meta["source_status"] = "cache_refreshed_from_mcp" if generation_meta.get("mcp_called_for_cache_miss") else "mcp_preflight_success"
            else:
                generation_meta["source_status"] = "mcp_failed_no_basis"

    if generation_meta is not None and generation_meta.get("tier_resolved") == 3:
        from policies.answer_builder_policy import build_agency_specific_legal_review_answer
        answer = build_agency_specific_legal_review_answer(generation_meta, answer)

    # 대화 이력 업데이트
    history.append({"role": "user", "text": user_message})
    history.append({"role": "model", "text": answer})

    # API 레이어용 generation_meta 저장
    if generation_meta is not None:
        # [Phase 3 보완] 최종 단계에서 반드시 1회 계산 (어떤 경로든 무조건 채워짐)
        if not generation_meta.get("source_status"):
            _tier = generation_meta.get("tier_resolved", 1)
            if _tier == 0:
                generation_meta["source_status"] = "no_mcp_required"
            else:
                generation_meta["source_status"] = "mcp_failed_no_basis"

        # [Phase 7-A] tool_elapsed_ms_by_name 집계 (Tier 0 이외 경로에서도 기록)
        if "tool_elapsed_ms_by_name" not in generation_meta and all_tool_results:
            _te_by_name = {}
            for _tr in all_tool_results:
                _tn = _tr.get("tool_name", "unknown")
                _te_by_name[_tn] = _te_by_name.get(_tn, 0) + _tr.get("elapsed_ms", 0)
            generation_meta["tool_elapsed_ms_by_name"] = _te_by_name

        # [Phase 7-A] tool_args_log 집계 (Tier 0 이외 경로에서도 기록)
        if "tool_args_log" not in generation_meta and all_tool_results:
            generation_meta["tool_args_log"] = [
                {"tool": _tr.get("tool_name", "unknown"), "args": _tr.get("tool_args", {})}
                for _tr in all_tool_results
            ]

        # [Phase 7-A] 필수 필드 기본값 보장
        generation_meta.setdefault("tool_elapsed_ms_by_name", {})
        generation_meta.setdefault("tool_args_log", [])
        generation_meta.setdefault("source_call_statuses", source_call_statuses)
        generation_meta.setdefault("classified_candidate_count", 0)
        generation_meta.setdefault("formatter_input_count", 0)
        generation_meta.setdefault("formatter_output_chars", 0)
        generation_meta.setdefault("candidate_table_source", "none")

        _last_generation_meta = dict(generation_meta)
        print("!!! GLOBAL META UPDATED TO:", list(_last_generation_meta.keys()))
    else:
        _last_generation_meta = {
            "prompt_mode": "legacy",
            "candidate_table_source": "none",
            "legal_conclusion_allowed": False,
            "final_answer_scanned": True,
            "model_used": MODEL_ID,
        }
        
    if "query_tier" in globals() or "query_tier" in locals():
        _last_generation_meta["tier_resolved"] = locals().get("query_tier", 1)
        _last_generation_meta["mandatory_mcp_plan"] = locals().get("mandatory_mcp_plan", [])
        _last_generation_meta["mandatory_mcp_executed"] = locals().get("mandatory_mcp_executed", [])
        _last_generation_meta["mandatory_mcp_missing"] = locals().get("mandatory_mcp_missing", [])
        _last_generation_meta["answer_schema_version"] = "regional_procurement_v2"


    return answer, history


def get_last_generation_meta() -> dict:
    """마지막 chat() 호출의 generation_meta를 반환. API 레이어용."""
    return dict(_last_generation_meta)


# ─────────────────────────────────────────────
# 독립 유틸리티 (chat() 밖)
# ─────────────────────────────────────────────

def _parse_amount(text: str):
    """
    자연어 금액 파싱. 복합 단위도 지원.
    - 7천만원 → 70_000_000
    - 7000만원 → 70_000_000
    - 70,000,000원 → 70_000_000
    - 70000000원 → 70_000_000
    - 1억 → 100_000_000
    - 1억5천만원 → 150_000_000
    - 2천만원 → 20_000_000
    """
    t = text.replace(" ", "").replace(",", "")

    # 4천5백만원, 1억4천5백만원 등 복합 만원 단위.
    # 일반 "N백만원" 패턴보다 먼저 처리해야 4천5백만원을 500만원으로 오인하지 않는다.
    m_korean_man = re.search(r'(?:(\d+(?:\.\d+)?)억)?(?:(\d+(?:\.\d+)?)천)?(?:(\d+(?:\.\d+)?)백)?만원', t)
    if m_korean_man and any(m_korean_man.group(i) for i in (1, 2, 3)):
        total = 0.0
        if m_korean_man.group(1):
            total += float(m_korean_man.group(1)) * 100_000_000
        if m_korean_man.group(2):
            total += float(m_korean_man.group(2)) * 10_000_000
        if m_korean_man.group(3):
            total += float(m_korean_man.group(3)) * 1_000_000
        return int(total)

    # 1) 복합: N억M천만원, N억M만원 등
    m_comp = re.search(r'(\d+)억(\d+)(천만|백만|만)원', t)
    if m_comp:
        total = int(m_comp.group(1)) * 100_000_000
        n2 = int(m_comp.group(2))
        u2 = m_comp.group(3)
        if u2 == '천만':
            total += n2 * 10_000_000
        elif u2 == '백만':
            total += n2 * 1_000_000
        elif u2 == '만':
            total += n2 * 10_000
        return total

    # 2) 단일 한글 단위: N억원, N천만원, N백만원, N만원
    m_single = re.search(r'(\d+)(억|천만|백만|만)원?', t)
    if m_single:
        n = int(m_single.group(1))
        u = m_single.group(2)
        if u == '억':
            return n * 100_000_000
        if u == '천만':
            return n * 10_000_000
        if u == '백만':
            return n * 1_000_000
        if u == '만':
            return n * 10_000

    # 3) 순수 숫자+원: 70000000원
    m_plain = re.search(r'(\d{5,})원', t)
    if m_plain:
        return int(m_plain.group(1))

    return None


def _detect_regional_preference(text: str) -> bool:
    """지역업체 활용 의도 감지"""
    REGIONAL_KEYWORDS = [
        "지역업체", "지역상품", "부산업체", "부산 업체", "부산 소재",
        "지역업체와 계약", "지역업체 활용", "지역업체랑",
        "부산업체 추천", "지역 제한", "지역제한",
        "부산업체랑", "지역업체한테", "부산업체한테",
    ]
    return any(kw in text for kw in REGIONAL_KEYWORDS)

# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=== AI 법령 챗봇 테스트 ===\n")
    test_q = "지역제한 입찰 기준 금액이 얼마야?"
    print(f"Q: {test_q}\n")
    answer, _ = chat(test_q)
    print(f"A:\n{answer}")

