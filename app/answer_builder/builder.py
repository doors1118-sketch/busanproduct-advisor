import re
from app.gateway.models.context import GatewayResponse
from app.rule_engine.decision_context import DecisionContext
from .schema import AnswerBuilderOutput, AnswerSection, CandidateTableSection, CandidateTableRow

FORBIDDEN_PHRASES = [
    "계약 가능합니다",
    "구매 가능합니다",
    "수의계약 가능합니다",
    "지역제한 가능합니다",
    "낙찰 가능합니다"
]

def check_forbidden_phrases(text: str) -> list[str]:
    found = []
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            found.append(phrase)
    return found

def get_summary_text(review_outcome: str) -> str:
    mapping = {
        "out_of_scope": "해당 질의는 관할 구역 외이거나 시스템 지원 범위 밖입니다.",
        "insufficient_data": "정확한 안내를 위해 추가 데이터(예: 계약 주체, 품목명 등)의 확인이 필요합니다.",
        "manual_review_required": "복수의 해석이 가능하여 수동 검토가 요구되는 사안입니다.",
        "conditional_review": "특정 조건(갱신 확인 등) 충족 여부에 대한 추가 검토가 권고됩니다.",
        "review_candidate": "제시된 조건을 기준으로 우선 검토 후보로 분류할 수 있으나, 계약 전 확인이 필요합니다.",
        "not_triggered": "특별한 자격 심사 로직이 발동되지 않은 일반 안내 대상입니다."
    }
    return mapping.get(review_outcome, "검토 상태를 확인할 수 없습니다.")

def build_answer(gateway_response: GatewayResponse, decision_context: DecisionContext) -> AnswerBuilderOutput:
    # 1. Summary Section
    summary = AnswerSection(
        title="요약",
        content=get_summary_text(decision_context.review_outcome)
    )
    
    # 1-1. Local Purchase Support Review Section
    local_support_section = AnswerSection(
        title="지역업체 지원 및 우선구매 검토 경로",
        content="안전하고 효과적인 계약 진행을 위해 다음의 제도 활용 가능성을 확인하시기 바랍니다.",
        bullets=[
            "지역제한 경쟁입찰 검토",
            "지역의무공동도급 검토",
            "지역업체 참여도 가점 검토",
            "지역상품 우선구매 조례·시책 검토",
            "수의계약 활용 가능성 검토",
            "정책기업 우대·우선구매 검토",
            "MAS·종합쇼핑몰 내 지역업체 후보 활용 검토",
            "품목별 중기경쟁제품·직접생산확인 추가 검토"
        ]
    )
    
    # 2. Item Eligibility Section
    item_section = None
    if decision_context.item_eligibility_grade == "explicit":
        item_section = AnswerSection(
            title="품목 자격 안내",
            content="품목별 세부 자격 조건을 확인하시기 바랍니다."
        )
    elif decision_context.item_eligibility_grade == "silent":
        summary.bullets.append("해당 품목이 중소기업자간 경쟁제품으로 특정되면 직접생산확인 검토가 필요할 수 있습니다.")
    elif decision_context.item_eligibility_status == "ambiguous" or (decision_context.review_outcome == "manual_review_required" and decision_context.item_eligibility_status == "ambiguous"):
        item_section = AnswerSection(
            title="품목 자격 안내",
            content="세부품명 확정이 불가합니다. 정확한 품번/품명을 확인해주시기 바랍니다."
        )
        
    # 3. Procedure Guidance Section
    procedure_section = None
    if gateway_response.procedure_context and gateway_response.procedure_context.sources:
        bullets = [s.source_name for s in gateway_response.procedure_context.sources]
        procedure_section = AnswerSection(
            title="절차 안내",
            content="다음 절차를 참고하시기 바랍니다.",
            bullets=bullets
        )
        
    # 4. Route Review Section
    route_section = None
    if decision_context.dual_routing_active:
        route_section = AnswerSection(
            title="조달 경로 안내",
            content="MAS 단가계약 등 특수 조달 경로가 적용될 수 있습니다."
        )
        
    # 5. Candidate Table Section
    candidate_section = None
    comp_ctx = gateway_response.company_candidate_context
    if comp_ctx and comp_ctx.candidates:
        rows = []
        for c in comp_ctx.candidates:
            enrichment_info = None
            if c.enrichment_data:
                cert_status = c.enrichment_data.cert_status
                if cert_status == "valid":
                    enrichment_info = "참고: 직생증명서 보유"
                elif cert_status == "expired":
                    enrichment_info = "참고: 직생증명서 만료"
                else:
                    enrichment_info = "참고: 직생증명서 상태 미확인"
                    
            rows.append(CandidateTableRow(
                company_name_masked=c.company_name_masked,
                location=c.location,
                business_type=c.business_type,
                enrichment_info=enrichment_info
            ))
        candidate_section = CandidateTableSection(
            title="후보 업체 표",
            description="참고용 업체 정보입니다.",
            rows=rows
        )
        
    # 6. Caution & Disclaimer
    caution = AnswerSection(
        title="주의사항",
        content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다."
    )
    disclaimer = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."
    
    # 7. Render Markdown (Skeleton rendering)
    rendered_parts = []
    rendered_parts.append(f"## {summary.title}\n{summary.content}")
    for b in summary.bullets:
        rendered_parts.append(f"- {b}")
        
    if local_support_section:
        rendered_parts.append(f"## {local_support_section.title}\n{local_support_section.content}")
        for b in local_support_section.bullets:
            rendered_parts.append(f"- {b}")
            
    if route_section:
        rendered_parts.append(f"## {route_section.title}\n{route_section.content}")
        
    if item_section:
        rendered_parts.append(f"## {item_section.title}\n{item_section.content}")
        
    if procedure_section:
        rendered_parts.append(f"## {procedure_section.title}\n{procedure_section.content}")
        for b in procedure_section.bullets:
            rendered_parts.append(f"- {b}")
        
    if candidate_section:
        rendered_parts.append(f"## {candidate_section.title}\n{candidate_section.description}")
        for r in candidate_section.rows:
            info = f" ({r.enrichment_info})" if r.enrichment_info else ""
            rendered_parts.append(f"- {r.company_name_masked} / {r.location}{info}")
            
    rendered_parts.append(f"## {caution.title}\n{caution.content}")
    rendered_parts.append(f"\n*{disclaimer}*")
    
    rendered_markdown = "\n\n".join(rendered_parts)
    
    # 8. Scan for forbidden phrases
    blocked = check_forbidden_phrases(rendered_markdown)
    
    out = AnswerBuilderOutput(
        summary_section=summary,
        local_purchase_support_review_section=local_support_section,
        route_review_section=route_section,
        item_eligibility_section=item_section,
        procedure_guidance_section=procedure_section,
        candidate_table_section=candidate_section,
        caution_section=caution,
        disclaimer=disclaimer,
        rendered_markdown=rendered_markdown,
        forbidden_phrase_scan_passed=len(blocked) == 0,
        blocked_phrases_found=blocked,
        fallback_applied=False
    )
    
    if len(blocked) > 0:
        out.fallback_applied = True
        out.summary_section.content = "내부 검토 로직에 따라 안전한 답변 생성을 위해 일시적으로 답변이 제한되었습니다."
        out.summary_section.bullets = []
        out.local_purchase_support_review_section = None
        out.item_eligibility_section = None
        out.procedure_guidance_section = None
        out.candidate_table_section = None
        out.route_review_section = None
        
        fallback_markdown = f"## 요약\n{out.summary_section.content}\n\n## 주의사항\n{out.caution_section.content}\n\n*{out.disclaimer}*"
        out.rendered_markdown = fallback_markdown
        
    return out
