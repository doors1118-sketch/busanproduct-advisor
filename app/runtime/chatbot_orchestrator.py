"""
Chatbot Runtime Orchestrator

사용자 질문 하나가 들어왔을 때, 내부 파이프라인을 순서대로 호출하고
최종적으로 하나의 구조화된 응답 객체를 반환한다.

파이프라인:
User Query → Intent Router → Gateway (stub) → Rule Engine (stub)
           → Company API Adapter → Answer Type Router → Runtime Response

이 모듈은 최종 법적 판단을 생성하지 않는다.
"""
import json
from typing import Optional

from app.router.gemini_intent_router import GeminiIntentRouter
from app.router.intent_schema import RouterResult
from app.answer_builder.answer_type_router import route_answer, FORBIDDEN_PHRASES
from app.answer_builder.schema import AnswerSection, AnswerBuilderOutput, CandidateTableSection, CandidateTableRow
from app.runtime.runtime_schema import (
    ChatbotRuntimeRequest,
    ChatbotRuntimeResponse,
    RuntimeStageResult,
)
from app.runtime.company_api_adapter import CompanyAPIAdapter, CompanyCandidateResult

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


def _render_candidate_table(company_result: CompanyCandidateResult, answer_output: AnswerBuilderOutput) -> AnswerBuilderOutput:
    """Company API 결과를 answer_output에 후보표 섹션으로 추가한다."""
    if company_result.status != "success" or not company_result.candidates:
        return answer_output

    rows = []
    for c in company_result.candidates:
        rows.append(CandidateTableRow(
            company_name_masked=c.company_name_masked,
            location=c.location,
            business_type=c.business_type,
            enrichment_info=f"주요품목: {', '.join(c.main_products)}" if c.main_products else None
        ))

    table = CandidateTableSection(
        title="검토 후보 업체",
        description=f"아래 업체는 검색 조건({company_result.search_query})에 따른 검토 후보입니다. 적격 여부는 별도 확인이 필요합니다.",
        rows=rows
    )
    answer_output.candidate_table_section = table

    # rendered_markdown에 후보표 추가
    table_md_parts = [f"\n\n## {table.title}\n{table.description}"]
    for r in rows:
        info = f" ({r.enrichment_info})" if r.enrichment_info else ""
        table_md_parts.append(f"- {r.company_name_masked} / {r.location}{info}")
    table_md_parts.append(f"\n총 {company_result.total_found}건 조회됨 (상위 {len(rows)}건 표시)")

    # 주의사항 앞에 삽입
    caution_marker = "\n\n## 주의사항"
    if caution_marker in answer_output.rendered_markdown:
        answer_output.rendered_markdown = answer_output.rendered_markdown.replace(
            caution_marker,
            "\n".join(table_md_parts) + caution_marker
        )
    else:
        answer_output.rendered_markdown += "\n".join(table_md_parts)

    return answer_output


class ChatbotRuntimeOrchestrator:
    def __init__(self, use_mock_company_api: bool = True):
        self.router = GeminiIntentRouter()
        self.company_adapter = CompanyAPIAdapter(use_mock=use_mock_company_api)

    def run(self, request: ChatbotRuntimeRequest) -> ChatbotRuntimeResponse:
        stages = []
        errors = []
        router_result: Optional[RouterResult] = None
        answer_output: Optional[AnswerBuilderOutput] = None
        company_result: Optional[CompanyCandidateResult] = None

        # ── Stage 1: Intent Router ──
        try:
            if request.mock_gemini_response is not None:
                raw = json.dumps(request.mock_gemini_response, ensure_ascii=False)
            else:
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
            reason="Gateway integration deferred",
        ))

        # ── Stage 3: Rule Engine (stub) ──
        stages.append(RuntimeStageResult(
            stage_name="rule_engine",
            status="skipped",
            skipped=True,
            reason="Rule Engine deep integration deferred",
        ))

        # ── Stage 4: Company Candidate Resolver ──
        try:
            company_result = self.company_adapter.resolve(router_result)
            if company_result.status == "skipped":
                stages.append(RuntimeStageResult(
                    stage_name="company_candidate_resolver",
                    status="skipped",
                    skipped=True,
                    reason=company_result.error or "candidate_lookup_required=False"
                ))
            elif company_result.status == "failed":
                stages.append(RuntimeStageResult(
                    stage_name="company_candidate_resolver",
                    status="failed",
                    skipped=False,
                    reason=company_result.error
                ))
                errors.append(f"company_candidate_resolver: {company_result.error}")
            else:
                stages.append(RuntimeStageResult(
                    stage_name="company_candidate_resolver",
                    status="success",
                    skipped=False
                ))
        except Exception as e:
            stages.append(RuntimeStageResult(
                stage_name="company_candidate_resolver",
                status="failed",
                skipped=False,
                reason=str(e)
            ))
            errors.append(f"company_candidate_resolver: {str(e)}")

        # ── Stage 5: Answer Builder ──
        try:
            answer_output = route_answer(router_result)

            # Company API 결과가 있으면 후보표 추가
            if company_result and company_result.status == "success" and company_result.candidates:
                answer_output = _render_candidate_table(company_result, answer_output)

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

        # ── Forbidden phrase scan ──
        if not answer_output.forbidden_phrase_scan_passed:
            errors.append("forbidden_phrase_scan: blocked phrases detected")

        # ── Runtime Status 산출 ──
        failed_stages = [s for s in stages if s.status == "failed"]

        if failed_stages:
            runtime_status = "failed" if answer_output.fallback_applied else "degraded"
        elif not answer_output.forbidden_phrase_scan_passed or answer_output.fallback_applied:
            runtime_status = "degraded"
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
