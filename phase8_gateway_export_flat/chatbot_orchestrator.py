"""
Phase 10.4: Chatbot Runtime Orchestrator

사용자 질문 하나가 들어왔을 때, 내부 파이프라인을 순서대로 호출하고
최종적으로 하나의 구조화된 응답 객체를 반환한다.

파이프라인:
User Query → Intent Router → Gateway (stub) → Rule Engine (stub)
           → Answer Type Router → Answer Builder Output → Runtime Response

이 모듈은 최종 법적 판단을 생성하지 않는다.
"""
import json
import traceback
from typing import Optional

from app.router.gemini_intent_router import GeminiIntentRouter
from app.router.intent_schema import RouterResult
from app.answer_builder.answer_type_router import route_answer, FORBIDDEN_PHRASES
from app.answer_builder.schema import AnswerSection, AnswerBuilderOutput
from app.runtime.runtime_schema import (
    ChatbotRuntimeRequest,
    ChatbotRuntimeResponse,
    RuntimeStageResult,
)

FALLBACK_MESSAGE = "질의 의도 또는 필수 정보가 불명확하여 추가 확인이 필요합니다."
DISCLAIMER = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."


def _fallback_answer() -> AnswerBuilderOutput:
    """안전한 fallback 응답 생성."""
    summary = AnswerSection(title="안내", content=FALLBACK_MESSAGE)
    caution = AnswerSection(title="주의사항", content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다.")
    md = f"## 안내\n{FALLBACK_MESSAGE}\n\n## 주의사항\n{caution.content}\n\n*{DISCLAIMER}*"
    return AnswerBuilderOutput(
        summary_section=summary,
        caution_section=caution,
        disclaimer=DISCLAIMER,
        rendered_markdown=md,
        forbidden_phrase_scan_passed=True,
        blocked_phrases_found=[],
        fallback_applied=True,
    )


def _fallback_router_result() -> RouterResult:
    return RouterResult(
        primary_intent="out_of_scope",
        routing_decision="clarification_required",
        reason="Runtime fallback",
    )


class ChatbotRuntimeOrchestrator:
    def __init__(self):
        self.router = GeminiIntentRouter()

    def run(self, request: ChatbotRuntimeRequest) -> ChatbotRuntimeResponse:
        stages = []
        errors = []
        router_result: Optional[RouterResult] = None
        answer_output: Optional[AnswerBuilderOutput] = None

        # ── Stage 1: Intent Router ──
        try:
            if request.mock_gemini_response is not None:
                raw = json.dumps(request.mock_gemini_response, ensure_ascii=False)
            else:
                # 실제 Gemini API 호출은 후속 단계에서 구현
                raw = json.dumps({"primary_intent": "out_of_scope", "confidence": 0.3, "slots": {}})

            router_result = self.router.parse_gemini_response(request.user_query, raw)

            stages.append(RuntimeStageResult(
                stage_name="intent_router", status="success", skipped=False
            ))
        except Exception as e:
            stages.append(RuntimeStageResult(
                stage_name="intent_router", status="failed", skipped=False, reason=str(e)
            ))
            errors.append(f"intent_router: {str(e)}")

        # Fail-closed: router 실패 시 fallback
        if router_result is None:
            return ChatbotRuntimeResponse(
                user_query=request.user_query,
                router_result=_fallback_router_result(),
                answer_output=_fallback_answer(),
                runtime_stages=stages,
                runtime_status="failed",
                fallback_applied=True,
                errors=errors,
            )

        # ── Stage 2: Gateway Context Resolver (stub) ──
        stages.append(RuntimeStageResult(
            stage_name="gateway_context",
            status="skipped",
            skipped=True,
            reason="Gateway integration deferred in Phase 10.4",
        ))

        # ── Stage 3: Rule Engine (stub) ──
        stages.append(RuntimeStageResult(
            stage_name="rule_engine",
            status="skipped",
            skipped=True,
            reason="Rule Engine deep integration deferred in Phase 10.4",
        ))

        # ── Stage 4: Answer Builder ──
        try:
            answer_output = route_answer(router_result)
            stages.append(RuntimeStageResult(
                stage_name="answer_builder", status="success", skipped=False
            ))
        except Exception as e:
            stages.append(RuntimeStageResult(
                stage_name="answer_builder", status="failed", skipped=False, reason=str(e)
            ))
            errors.append(f"answer_builder: {str(e)}")

        # Fail-closed: answer 생성 실패 시 fallback
        if answer_output is None:
            return ChatbotRuntimeResponse(
                user_query=request.user_query,
                router_result=router_result,
                answer_output=_fallback_answer(),
                runtime_stages=stages,
                runtime_status="failed",
                fallback_applied=True,
                errors=errors,
            )

        # ── Stage 5: Forbidden phrase scan (이미 answer_output 내부에서 수행됨) ──
        if not answer_output.forbidden_phrase_scan_passed:
            errors.append("forbidden_phrase_scan: blocked phrases detected")

        # ── Runtime Status 산출 ──
        failed_stages = [s for s in stages if s.status == "failed"]
        skipped_stages = [s for s in stages if s.skipped]

        if failed_stages:
            runtime_status = "failed" if answer_output.fallback_applied else "degraded"
        elif skipped_stages:
            # Gateway/RuleEngine 의도적 skip은 정상
            runtime_status = "success"
        else:
            runtime_status = "success"

        return ChatbotRuntimeResponse(
            user_query=request.user_query,
            router_result=router_result,
            gateway_response=None,
            decision_context=None,
            answer_output=answer_output,
            runtime_stages=stages,
            runtime_status=runtime_status,
            fallback_applied=answer_output.fallback_applied,
            errors=errors,
        )


def run_chatbot_runtime(request: ChatbotRuntimeRequest) -> ChatbotRuntimeResponse:
    """함수형 진입점."""
    return ChatbotRuntimeOrchestrator().run(request)
