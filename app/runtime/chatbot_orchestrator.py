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
        biz = f" / {r.business_type}" if r.business_type else ""
        table_md_parts.append(f"- {r.company_name_masked} / {r.location}{biz} / 상태: 검토 후보, 적격 확인 필요{info}")
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

        # ── Stage 2.5: Item Eligibility Resolver ──
        item_eligibility_context = None
        try:
            from phase8_gateway_export_flat.item_eligibility_adapter import ItemEligibilityAdapter
            adapter = ItemEligibilityAdapter()
            item_name = router_result.slots.item_name if hasattr(router_result.slots, 'item_name') else None
            detail_item_code = router_result.slots.detail_item_code if hasattr(router_result.slots, 'detail_item_code') else None
            company_id = router_result.slots.company_id if hasattr(router_result.slots, 'company_id') else None
            
            eligibility_result = adapter.resolve(item_name=item_name, detail_item_code=detail_item_code, company_id=company_id)
            if eligibility_result.resolver_status != "not_triggered":
                item_eligibility_context = eligibility_result.context
                stages.append(RuntimeStageResult(
                    stage_name="item_eligibility",
                    status="success"
                ))
            else:
                stages.append(RuntimeStageResult(stage_name="item_eligibility", status="success", skipped=True))
        except Exception as e:
            import traceback
            import logging
            logging.exception("Item Eligibility Resolver Error")
            stages.append(RuntimeStageResult(stage_name="item_eligibility", status="failed", reason=str(e)))
            errors.append(f"item_eligibility: {str(e)}")

        # ── Stage 3: Amount Layer (Rule Engine) ──
        active_rule_ids = None
        threshold_ref_used = None
        threshold_value_used = None
        try:
            from phase8_gateway_export_flat.amount_layer import resolve_active_rules
            slots_dict = router_result.slots.model_dump()
            
            source_map = None
            source_map_path = request.runtime_options.get("source_map_path") if request.runtime_options else None
            if source_map_path:
                with open(source_map_path, "r", encoding="utf-8") as f:
                    source_map = json.load(f)
            
            if request.runtime_options and request.runtime_options.get("review_all_routes"):
                slots_dict["review_all_routes"] = True
            amount_result = resolve_active_rules(slots_dict, source_map=source_map)
            active_rule_ids = amount_result.get("active_rule_ids", [])
            threshold_ref_used = amount_result.get("threshold_ref_used")
            threshold_value_used = amount_result.get("threshold_value_used")
            
            # R_EXPLICIT_ITEM_ELIGIBILITY 강제 주입
            if item_eligibility_context and "R_EXPLICIT_ITEM_ELIGIBILITY" not in active_rule_ids:
                active_rule_ids.append("R_EXPLICIT_ITEM_ELIGIBILITY")

            stages.append(RuntimeStageResult(
                stage_name="rule_engine",
                status="success",
                skipped=False
            ))
        except Exception as e:
            stages.append(RuntimeStageResult(
                stage_name="rule_engine",
                status="failed",
                skipped=False,
                reason=str(e)
            ))
            errors.append(f"rule_engine: {str(e)}")

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
            elif company_result.status == "empty":
                stages.append(RuntimeStageResult(
                    stage_name="company_candidate_resolver",
                    status="success",
                    skipped=False,
                    reason="검색 조건에 해당하는 후보업체 없음"
                ))
            else:
                stages.append(RuntimeStageResult(
                    stage_name="company_candidate_resolver",
                    status=company_result.status,
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

        # ── Stage 5: Evidence Context (optional) ──
        evidence_context = None
        opts = request.runtime_options or {}
        use_evidence = opts.get("use_evidence_builder", False)
        source_map_path = opts.get("source_map_path", None)

        if use_evidence:
            try:
                from phase8_gateway_export_flat.evidence_context_loader import build_evidence_context
                evidence_context = build_evidence_context(
                    router_result, 
                    source_map_path=source_map_path,
                    active_rule_ids=active_rule_ids,
                    threshold_ref_used=threshold_ref_used,
                    threshold_value_used=threshold_value_used
                )
                stages.append(RuntimeStageResult(
                    stage_name="evidence_context", status="success", skipped=False
                ))
            except Exception as e:
                stages.append(RuntimeStageResult(
                    stage_name="evidence_context", status="failed", skipped=False, reason=str(e)
                ))
                errors.append(f"evidence_context: {str(e)}")
                # evidence 실패 시 기존 route_answer로 fallback — runtime 중단 안 함
        else:
            stages.append(RuntimeStageResult(
                stage_name="evidence_context", status="skipped", skipped=True,
                reason="use_evidence_builder=False"
            ))

        # ── Stage 6: Answer Builder ──
        try:
            answer_output = route_answer(
                router_result, 
                evidence_context=evidence_context,
                item_eligibility_context=item_eligibility_context
            )

            # Company API 결과가 있으면 후보표 추가
            if company_result and company_result.status == "success" and company_result.candidates:
                answer_output = _render_candidate_table(company_result, answer_output)
            # 중복 파이프라인 방지: Final Forbidden Phrase Scan은 하단(Line 297)에서 통합 처리

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

        # ── Forbidden phrase re-scan (후보표 추가 후 재검사) ──
        blocked = [p for p in FORBIDDEN_PHRASES if p in answer_output.rendered_markdown]
        if blocked:
            existing_blocked = set(answer_output.blocked_phrases_found)
            existing_blocked.update(blocked)
            answer_output.blocked_phrases_found = list(existing_blocked)
            answer_output.forbidden_phrase_scan_passed = False
        if blocked:
            answer_output.fallback_applied = True
            answer_output.rendered_markdown = (
                "## 안내\n"
                "내부 검토 로직에 따라 안전한 답변 생성을 위해 "
                "일시적으로 답변이 제한되었습니다.\n\n"
                "## 주의사항\n"
                "정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다.\n\n"
                f"*{DISCLAIMER}*"
            )
            answer_output.candidate_table_section = None
            answer_output.local_purchase_support_review_section = None
            answer_output.route_review_section = None
            answer_output.item_eligibility_section = None
            answer_output.procedure_guidance_section = None
            errors.append(f"forbidden_phrase_rescan: {blocked}")

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
    """함수형 진입점. runtime_options로 Company API, Evidence Builder 전환 가능."""
    opts = request.runtime_options or {}
    use_mock_company_api = opts.get("use_mock_company_api", True)
    return ChatbotRuntimeOrchestrator(
        use_mock_company_api=use_mock_company_api
    ).run(request)
