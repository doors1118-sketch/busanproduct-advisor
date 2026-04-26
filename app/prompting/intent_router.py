"""
LLM Intent Router — gemini-2.0-flash 기반 의도 분류
Pre-Router fast path: 명확 단일 유형이면 LLM 호출 생략
"""
import os
import json
from google import genai
from google.genai import types
from .schemas import KeywordRouteResult, IntentRouteResult, IntentCandidate

_PROMPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "prompts",
)
ROUTER_MODEL = os.getenv("ROUTER_MODEL", "gemini-2.5-flash")

_router_prompt: str = ""

def _load_router_prompt() -> str:
    global _router_prompt
    if _router_prompt:
        return _router_prompt
    path = os.path.join(_PROMPTS_DIR, "intent_router.md")
    with open(path, "r", encoding="utf-8") as f:
        _router_prompt = f.read()
    return _router_prompt


def classify_intent(
    question: str,
    keyword_result: KeywordRouteResult,
    router_client: genai.Client,
) -> IntentRouteResult:
    """
    2단계 Intent Router.
    - fast path: keyword_result.is_unambiguous이면 LLM 호출 skip
    - normal path: gemini-2.0-flash로 분류
    - 실패 fallback: Pre-Router + common/mixed
    """
    # ─── MCP 강제 할당 (키워드 기반) ───
    mcp_keywords = ["금액", "한도", "수의계약", "가능 여부", "규정", "조례", "판례", "해석례"]
    force_mcp = any(k in question for k in mcp_keywords)

    # ─── Fast path ───
    if keyword_result.is_unambiguous:
        cat = keyword_result.matched_categories[0]
        return IntentRouteResult(
            candidates=[IntentCandidate(label=cat, confidence=0.95)],
            agency_type="local_government",
            needs_clarification=None,
            mcp_required=True if force_mcp else True, # Default was True, but making it explicit
            router_status="skipped",
        )

    # ─── Normal path: LLM 호출 ───
    try:
        prompt_text = _load_router_prompt()
        kw_info = (
            f"Keyword Pre-Router 결과:\n"
            f"  matched: {keyword_result.matched_categories}\n"
            f"  ambiguous: {keyword_result.ambiguous_keywords}\n"
        )

        response = router_client.models.generate_content(
            model=ROUTER_MODEL,
            contents=[
                types.Content(role="user", parts=[
                    types.Part.from_text(text=f"{kw_info}\n사용자 질문: {question}")
                ])
            ],
            config=types.GenerateContentConfig(
                system_instruction=prompt_text,
                temperature=0.0,
            ),
        )

        raw_text = response.candidates[0].content.parts[0].text
        # JSON 추출 (```json ... ``` 래핑 대응)
        json_str = raw_text
        if "```" in raw_text:
            start = raw_text.find("{")
            end = raw_text.rfind("}") + 1
            if start >= 0 and end > start:
                json_str = raw_text[start:end]

        data = json.loads(json_str)
        candidates = [
            IntentCandidate(label=c["label"], confidence=c["confidence"])
            for c in data.get("candidates", [])
        ]
        if not candidates:
            raise ValueError("No candidates in router response")

        return IntentRouteResult(
            candidates=candidates,
            agency_type=data.get("agency_type", "local_government"),
            needs_clarification=data.get("needs_clarification"),
            mcp_required=True if force_mcp else data.get("mcp_required", True),
            router_status="success",
        )

    except Exception as e:
        print(f"  [ROUTER] LLM Intent Router failed: {e}")
        # ─── Fallback: Pre-Router + common/mixed ───
        fallback_candidates = [
            IntentCandidate(label=cat, confidence=0.50)
            for cat in keyword_result.matched_categories
        ]
        if not fallback_candidates:
            fallback_candidates = [IntentCandidate(label="unclear", confidence=0.30)]

        return IntentRouteResult(
            candidates=fallback_candidates,
            agency_type="local_government",
            needs_clarification=None,
            mcp_required=True if force_mcp else True,
            router_status="failed",
        )
