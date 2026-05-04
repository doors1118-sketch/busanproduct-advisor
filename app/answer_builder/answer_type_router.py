"""
Phase 10.2: Answer Type Router

RouterResult.routing_decision 값에 따라 적절한 답변 빌더 함수를 선택하고,
flow별로 포함/제외할 섹션을 결정한다.

이 모듈은 최종 법적 판단을 생성하지 않는다.
"""

from app.router.intent_schema import RouterResult
from app.answer_builder.schema import AnswerSection, AnswerBuilderOutput, CandidateTableSection

FORBIDDEN_PHRASES = [
    "계약 가능합니다",
    "구매 가능합니다",
    "수의계약 가능합니다",
    "지역제한 가능합니다",
    "낙찰 가능합니다"
]

def _check_forbidden(text: str) -> list[str]:
    return [p for p in FORBIDDEN_PHRASES if p in text]

def _render_markdown(sections: list[AnswerSection], disclaimer: str) -> str:
    parts = []
    for s in sections:
        parts.append(f"## {s.title}\n{s.content}")
        for b in s.bullets:
            parts.append(f"- {b}")
    parts.append(f"\n*{disclaimer}*")
    return "\n\n".join(parts)

def _base_output(sections: list[AnswerSection], disclaimer: str) -> AnswerBuilderOutput:
    rendered = _render_markdown(sections, disclaimer)
    blocked = _check_forbidden(rendered)
    
    summary = sections[0] if sections else AnswerSection(title="요약", content="")
    caution = sections[-1] if len(sections) > 1 else AnswerSection(title="주의사항", content="")
    
    out = AnswerBuilderOutput(
        summary_section=summary,
        caution_section=caution,
        disclaimer=disclaimer,
        rendered_markdown=rendered,
        forbidden_phrase_scan_passed=len(blocked) == 0,
        blocked_phrases_found=blocked,
        fallback_applied=False
    )
    
    if blocked:
        out.fallback_applied = True
        out.summary_section.content = "내부 검토 로직에 따라 안전한 답변 생성을 위해 일시적으로 답변이 제한되었습니다."
        out.summary_section.bullets = []
        out.rendered_markdown = f"## 요약\n{out.summary_section.content}\n\n## 주의사항\n{caution.content}\n\n*{disclaimer}*"
        
    return out

# ─────────────────────────────────────────────
# Flow Builders
# ─────────────────────────────────────────────

def build_legal_explanation(router_result: RouterResult) -> AnswerBuilderOutput:
    """법령·제도 설명형 답변. 후보업체 조회 금지, 구매지원 섹션 자동 출력 금지."""
    disclaimer = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."
    
    topic = router_result.slots.legal_topic or "관련 제도"
    
    sections = [
        AnswerSection(
            title="법령·제도 설명",
            content=f"{topic}에 대한 설명입니다.",
            bullets=[]
        )
    ]
    
    # secondary intents를 참고 안내로만 표시
    if router_result.secondary_intents:
        ref_bullets = []
        for si in router_result.secondary_intents:
            if si == "procurement_route_review":
                ref_bullets.append("관련 조달경로(MAS, 제3자단가 등)에 대해서도 추가 확인이 가능합니다.")
            elif si == "local_purchase_support":
                ref_bullets.append("지역업체 구매지원 제도와 관련된 항목입니다. 구체적 구매 상황 시 별도 검토가 필요합니다.")
        if ref_bullets:
            sections.append(AnswerSection(
                title="참고 안내",
                content="아래 항목은 구체적 구매 상황에서 추가로 검토할 수 있는 사항입니다.",
                bullets=ref_bullets
            ))
    
    sections.append(AnswerSection(
        title="주의사항",
        content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다."
    ))
    
    return _base_output(sections, disclaimer)

def build_contract_review(router_result: RouterResult) -> AnswerBuilderOutput:
    """구체적 구매·계약 상황 검토 답변."""
    disclaimer = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."
    slots = router_result.slots
    
    # 1. 요약
    summary_bullets = []
    if slots.buyer_name:
        summary_bullets.append(f"기관: {slots.buyer_name}")
    if slots.amount:
        summary_bullets.append(f"추정가격: {slots.amount:,}원")
    if slots.item_name:
        summary_bullets.append(f"품목: {slots.item_name}")
    if slots.contract_object:
        summary_bullets.append(f"계약목적물: {slots.contract_object}")
    if slots.procurement_route:
        summary_bullets.append(f"조달경로: {slots.procurement_route}")
        
    sections = [
        AnswerSection(
            title="계약 검토 요약",
            content="아래 조건을 기준으로 계약 유형 및 절차를 검토합니다.",
            bullets=summary_bullets
        )
    ]
    
    # 2. 지역업체 구매지원 검토 (secondary에 있을 때만)
    if "local_purchase_support" in router_result.secondary_intents:
        support_bullets = [
            "지역제한 입찰 적용 가능 여부 확인 필요",
            "지역의무공동도급 적용 대상 여부 확인 필요",
            "지역업체 참여도 가점 적용 여부 확인 필요"
        ]
        sections.append(AnswerSection(
            title="지역업체 구매지원 제도 검토",
            content="지역업체 활용을 검토하기 위해 다음 구매지원 제도의 적용 여부를 확인해야 합니다.",
            bullets=support_bullets
        ))
        
    # 3. 조달경로 검토 (secondary에 있을 때)
    if "procurement_route_review" in router_result.secondary_intents:
        sections.append(AnswerSection(
            title="조달경로 검토",
            content="MAS, 종합쇼핑몰, 제3자단가계약 등 조달경로 적용 가능 여부를 확인해야 합니다."
        ))
    
    # 4. 품목 자격 검토 (secondary에 있을 때)
    if "item_eligibility" in router_result.secondary_intents:
        sections.append(AnswerSection(
            title="품목 자격 검토",
            content="중소기업자간 경쟁제품, 직접생산확인 등 품목 자격 요건 확인이 필요합니다."
        ))
    
    # 5. Source gap 안내
    sections.append(AnswerSection(
        title="확인 필요 사항",
        content="일부 세부 기준(금액 기준, 지역제한 비율 등)은 관련 법령·시행령 원문 확인이 필요합니다.",
        bullets=["수치 기준은 최신 법령 원문을 반드시 대조하시기 바랍니다."]
    ))
    
    sections.append(AnswerSection(
        title="주의사항",
        content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다."
    ))
    
    return _base_output(sections, disclaimer)

def build_candidate_search(router_result: RouterResult) -> AnswerBuilderOutput:
    """후보업체 조회 요청 답변. Company API 미연동이므로 placeholder 구조."""
    disclaimer = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."
    slots = router_result.slots
    
    sections = [
        AnswerSection(
            title="업체 후보 조회",
            content="요청하신 조건으로 업체 후보를 조회합니다.",
            bullets=[]
        )
    ]
    
    if slots.item_name:
        sections[0].bullets.append(f"검색 품목: {slots.item_name}")
    if slots.location:
        sections[0].bullets.append(f"지역: {slots.location}")
        
    # Placeholder: Company API 미연동
    sections.append(AnswerSection(
        title="조회 결과",
        content="현재 업체 후보 조회 API가 연동 대기 중입니다. 추후 업데이트 시 실제 후보 목록이 표시됩니다.",
        bullets=["(Company API 연동 예정)"]
    ))
    
    if "local_purchase_support" in router_result.secondary_intents:
        sections.append(AnswerSection(
            title="지역업체 구매지원 제도 참고",
            content="지역업체 활용 시 아래 구매지원 제도 적용 여부를 함께 검토하시기 바랍니다.",
            bullets=[
                "지역제한 입찰 적용 가능 여부",
                "지역의무공동도급 적용 대상 여부"
            ]
        ))
    
    sections.append(AnswerSection(
        title="주의사항",
        content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다."
    ))
    
    return _base_output(sections, disclaimer)

def build_mixed_flow(router_result: RouterResult) -> AnswerBuilderOutput:
    """복합 intent 답변. primary/secondary를 순서대로 섹션화."""
    disclaimer = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."
    
    # legal_explanation_only가 true이면 법령 설명 우선
    if router_result.legal_explanation_only:
        return build_legal_explanation(router_result)
    
    sections = [
        AnswerSection(
            title="복합 검토 요약",
            content="질문에 여러 검토 항목이 포함되어 있어 아래 순서로 안내합니다."
        )
    ]
    
    all_intents = [router_result.primary_intent] + router_result.secondary_intents
    
    if "procurement_route_review" in all_intents:
        route_name = router_result.slots.procurement_route or "조달경로"
        sections.append(AnswerSection(
            title="조달경로 검토",
            content=f"{route_name} 관련 조달경로 적용 여부를 확인해야 합니다."
        ))
        
    if "local_purchase_support" in all_intents:
        sections.append(AnswerSection(
            title="지역업체 구매지원 제도 검토",
            content="지역업체 활용을 검토하기 위해 다음 구매지원 제도의 적용 여부를 확인해야 합니다.",
            bullets=[
                "지역제한 입찰 적용 가능 여부 확인 필요",
                "지역의무공동도급 적용 대상 여부 확인 필요"
            ]
        ))
        
    if "candidate_search" in all_intents:
        sections.append(AnswerSection(
            title="업체 후보 조회",
            content="현재 업체 후보 조회 API가 연동 대기 중입니다.",
            bullets=["(Company API 연동 예정)"]
        ))
        
    if "item_eligibility" in all_intents:
        sections.append(AnswerSection(
            title="품목 자격 검토",
            content="중소기업자간 경쟁제품, 직접생산확인 등 품목 자격 요건 확인이 필요합니다."
        ))
    
    # Clarification
    if router_result.clarification_needed:
        sections.append(AnswerSection(
            title="추가 확인 필요",
            content="정확한 안내를 위해 아래 정보가 추가로 필요합니다.",
            bullets=router_result.clarification_needed
        ))
    
    sections.append(AnswerSection(
        title="주의사항",
        content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다."
    ))
    
    return _base_output(sections, disclaimer)

def build_out_of_scope(router_result: RouterResult) -> AnswerBuilderOutput:
    """지원 범위 밖 답변."""
    disclaimer = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."
    sections = [
        AnswerSection(title="안내", content="해당 질의는 시스템 지원 범위 밖입니다."),
        AnswerSection(title="주의사항", content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다.")
    ]
    return _base_output(sections, disclaimer)

def build_clarification(router_result: RouterResult) -> AnswerBuilderOutput:
    """추가 정보 요청 답변."""
    disclaimer = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."
    sections = [
        AnswerSection(
            title="추가 정보 요청",
            content="정확한 안내를 위해 아래 정보를 추가로 알려주시기 바랍니다.",
            bullets=router_result.clarification_needed if router_result.clarification_needed else ["질문을 더 구체적으로 입력해 주세요."]
        ),
        AnswerSection(title="주의사항", content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다.")
    ]
    return _base_output(sections, disclaimer)

# ─────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────

FLOW_MAP = {
    "legal_explanation_flow": build_legal_explanation,
    "contract_review_flow": build_contract_review,
    "local_purchase_support_flow": build_contract_review,  # 구매지원도 계약검토 구조 사용
    "candidate_search_flow": build_candidate_search,
    "item_eligibility_flow": build_contract_review,  # 품목자격도 계약검토 구조 내 섹션
    "procurement_route_review_flow": build_legal_explanation,  # 조달경로 설명은 법령설명 구조
    "mixed_flow": build_mixed_flow,
    "out_of_scope": build_out_of_scope,
    "clarification_required": build_clarification,
}

def route_answer(router_result: RouterResult) -> AnswerBuilderOutput:
    """RouterResult.routing_decision에 따라 적절한 빌더를 호출한다."""
    builder_fn = FLOW_MAP.get(router_result.routing_decision, build_out_of_scope)
    return builder_fn(router_result)
