"""
Phase 10.2: Answer Type Router v0.2

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

DISCLAIMER = "본 안내는 법적 효력이 없으며, 참고용으로만 제공됩니다."

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

def _build_output(
    sections: list[AnswerSection],
    disclaimer: str,
    local_purchase_support_review_section: AnswerSection = None,
    route_review_section: AnswerSection = None,
    item_eligibility_section: AnswerSection = None,
    procedure_guidance_section: AnswerSection = None,
    candidate_table_section: CandidateTableSection = None,
) -> AnswerBuilderOutput:
    rendered = _render_markdown(sections, disclaimer)
    blocked = _check_forbidden(rendered)

    summary = sections[0] if sections else AnswerSection(title="요약", content="")
    caution = next((s for s in sections if s.title == "주의사항"), AnswerSection(title="주의사항", content=""))

    out = AnswerBuilderOutput(
        summary_section=summary,
        caution_section=caution,
        disclaimer=disclaimer,
        rendered_markdown=rendered,
        local_purchase_support_review_section=local_purchase_support_review_section,
        route_review_section=route_review_section,
        item_eligibility_section=item_eligibility_section,
        procedure_guidance_section=procedure_guidance_section,
        candidate_table_section=candidate_table_section,
        forbidden_phrase_scan_passed=len(blocked) == 0,
        blocked_phrases_found=blocked,
        fallback_applied=False
    )

    if blocked:
        out.fallback_applied = True
        out.summary_section.content = "내부 검토 로직에 따라 안전한 답변 생성을 위해 일시적으로 답변이 제한되었습니다."
        out.summary_section.bullets = []
        out.local_purchase_support_review_section = None
        out.item_eligibility_section = None
        out.route_review_section = None
        out.procedure_guidance_section = None
        out.candidate_table_section = None
        out.rendered_markdown = f"## 요약\n{out.summary_section.content}\n\n## 주의사항\n{caution.content}\n\n*{disclaimer}*"

    return out

# ── Reusable section factories ──

def _local_support_section() -> AnswerSection:
    return AnswerSection(
        title="지역업체 구매지원 제도 검토",
        content="지역업체 활용을 검토하기 위해 다음 구매지원 제도의 적용 요건을 확인해야 합니다.",
        bullets=[
            "지역제한 입찰 적용 요건 확인",
            "지역의무공동도급 적용 대상 확인",
            "지역업체 참여도·평가항목 존재 여부 확인"
        ]
    )

def _route_review_section_obj(route_name: str = None) -> AnswerSection:
    name = route_name or "조달경로"
    return AnswerSection(
        title="조달경로 검토",
        content=f"{name} 관련 조달경로 적용 요건을 확인해야 합니다."
    )

def _item_eligibility_section_obj() -> AnswerSection:
    return AnswerSection(
        title="품목 자격 검토",
        content="중소기업자간 경쟁제품, 직접생산확인 등 품목 자격 요건 확인이 필요합니다."
    )

def _source_gap_section() -> AnswerSection:
    return AnswerSection(
        title="확인 필요 사항",
        content="일부 세부 기준(금액 기준, 지역제한 비율 등)은 관련 법령·시행령 원문 확인이 필요합니다.",
        bullets=["수치 기준은 최신 법령 원문을 반드시 대조하시기 바랍니다."]
    )

def _caution_section() -> AnswerSection:
    return AnswerSection(
        title="주의사항",
        content="정확한 판단은 관련 법령과 규정을 직접 확인하시기 바랍니다."
    )

COMPANY_TYPE_LABELS = {
    "women": "여성기업",
    "disabled": "장애인기업",
    "social": "사회적기업",
    "startup": "창업기업",
    "small_business": "소기업·소상공인",
    "general": "일반기업",
}

QUOTE_TYPE_LABELS = {
    "1_quote": "1인 견적",
    "2_quote": "2인 이상 견적",
}

CONTRACT_METHOD_LABELS = {
    "direct_contract": "수의계약 검토",
    "competitive_bid": "경쟁입찰 검토",
    "limited_competition": "제한경쟁 검토",
    "open_competition": "일반경쟁 검토",
}

# ─────────────────────────────────────────────
# Flow Builders
# ─────────────────────────────────────────────

def build_legal_explanation(router_result: RouterResult) -> AnswerBuilderOutput:
    """법령·제도 설명형 답변. 후보업체 조회 금지, 구매지원 섹션 자동 출력 금지."""
    topic = router_result.slots.legal_topic or "관련 제도"
    all_intents = [router_result.primary_intent] + router_result.secondary_intents

    sections = [
        AnswerSection(title="법령·제도 설명", content=f"{topic}에 대한 설명입니다.")
    ]

    # secondary intents를 참고 안내로만 표시
    ref_bullets = []
    if "procurement_route_review" in all_intents:
        ref_bullets.append("관련 조달경로(MAS, 제3자단가 등)에 대해서도 추가 확인이 가능합니다.")
    if "local_purchase_support" in all_intents:
        ref_bullets.append("지역업체 구매지원 제도와 관련된 항목입니다. 구체적 구매 상황 시 별도 검토가 필요합니다.")

    route_sec = None
    if ref_bullets:
        ref_section = AnswerSection(
            title="참고 안내",
            content="아래 항목은 구체적 구매 상황에서 추가로 검토할 수 있는 사항입니다.",
            bullets=ref_bullets
        )
        sections.append(ref_section)
        if "procurement_route_review" in all_intents:
            route_sec = ref_section

    sections.append(_caution_section())
    return _build_output(sections, DISCLAIMER, route_review_section=route_sec)


def build_contract_review(router_result: RouterResult) -> AnswerBuilderOutput:
    """구체적 구매·계약 상황 검토 답변."""
    slots = router_result.slots
    all_intents = [router_result.primary_intent] + router_result.secondary_intents

    # 1. 요약
    summary_bullets = []
    if slots.buyer_name:
        summary_bullets.append(f"기관: {slots.buyer_name}")
    if slots.amount:
        summary_bullets.append(f"추정가격: {slots.amount:,}원")
    if slots.item_name:
        summary_bullets.append(f"품목: {slots.item_name}")
    if slots.contract_object:
        obj_map = {"goods": "물품", "service": "용역", "construction": "공사"}
        obj_label = obj_map.get(slots.contract_object, slots.contract_object)
        summary_bullets.append(f"계약목적물: {obj_label}")
    if slots.company_type:
        summary_bullets.append(f"업체유형: {COMPANY_TYPE_LABELS.get(slots.company_type, slots.company_type)}")
    if slots.quote_type:
        summary_bullets.append(f"견적유형: {QUOTE_TYPE_LABELS.get(slots.quote_type, slots.quote_type)}")
    if slots.contract_method:
        summary_bullets.append(f"계약방식: {CONTRACT_METHOD_LABELS.get(slots.contract_method, slots.contract_method)}")
    if slots.procurement_route:
        summary_bullets.append(f"조달경로: {slots.procurement_route}")

    sections = [
        AnswerSection(title="계약 검토 요약", content="아래 조건을 기준으로 계약 유형 및 절차를 검토합니다.", bullets=summary_bullets)
    ]

    # 2. 지역업체 구매지원 (all_intents 기준)
    local_sec = None
    if "local_purchase_support" in all_intents:
        local_sec = _local_support_section()
        sections.append(local_sec)

    # 3. 조달경로 (all_intents 기준)
    route_sec = None
    if "procurement_route_review" in all_intents:
        route_sec = _route_review_section_obj(slots.procurement_route)
        sections.append(route_sec)

    # 4. 품목 자격 (all_intents 기준)
    item_sec = None
    if "item_eligibility" in all_intents:
        item_sec = _item_eligibility_section_obj()
        sections.append(item_sec)

    # 5. Source gap 안내
    sections.append(_source_gap_section())
    sections.append(_caution_section())

    return _build_output(
        sections, DISCLAIMER,
        local_purchase_support_review_section=local_sec,
        route_review_section=route_sec,
        item_eligibility_section=item_sec
    )


def build_candidate_search(router_result: RouterResult) -> AnswerBuilderOutput:
    """후보업체 조회 요청 답변. Company API 미연동이므로 placeholder 구조."""
    slots = router_result.slots
    all_intents = [router_result.primary_intent] + router_result.secondary_intents

    search_bullets = []
    if slots.item_name:
        search_bullets.append(f"검색 품목: {slots.item_name}")
    if slots.location:
        search_bullets.append(f"지역: {slots.location}")

    sections = [
        AnswerSection(
            title="업체 후보 조회 조건",
            content="요청하신 조건을 기준으로 향후 업체 후보 조회에 사용할 검색 조건을 정리합니다.",
            bullets=search_bullets
        ),
        AnswerSection(
            title="조회 결과",
            content="현재는 업체 후보 조회 API 연동 전이므로 실제 후보 목록은 표시하지 않습니다.",
            bullets=["(Company API 연동 예정)"]
        )
    ]

    local_sec = None
    if "local_purchase_support" in all_intents:
        local_sec = _local_support_section()
        sections.append(local_sec)

    sections.append(_caution_section())

    return _build_output(sections, DISCLAIMER, local_purchase_support_review_section=local_sec)


def build_mixed_flow(router_result: RouterResult) -> AnswerBuilderOutput:
    """복합 intent 답변. primary/secondary를 순서대로 섹션화."""
    if router_result.legal_explanation_only:
        return build_legal_explanation(router_result)

    all_intents = [router_result.primary_intent] + router_result.secondary_intents

    sections = [
        AnswerSection(title="복합 검토 요약", content="질문에 여러 검토 항목이 포함되어 있어 아래 순서로 안내합니다.")
    ]

    has_contract_info = bool(router_result.slots.amount or router_result.slots.item_name or router_result.slots.contract_object or router_result.slots.company_type or router_result.slots.quote_type)
    if "contract_review" in all_intents or has_contract_info:
        slots = router_result.slots
        summary_bullets = []
        if slots.amount:
            summary_bullets.append(f"추정가격: {slots.amount:,}원")
        if slots.item_name:
            summary_bullets.append(f"품목: {slots.item_name}")
        if slots.contract_object:
            obj_map = {"goods": "물품", "service": "용역", "construction": "공사"}
            obj_label = obj_map.get(slots.contract_object, slots.contract_object)
            summary_bullets.append(f"계약목적물: {obj_label}")
        if slots.company_type:
            summary_bullets.append(f"업체유형: {COMPANY_TYPE_LABELS.get(slots.company_type, slots.company_type)}")
        if slots.quote_type:
            summary_bullets.append(f"견적유형: {QUOTE_TYPE_LABELS.get(slots.quote_type, slots.quote_type)}")
        if slots.contract_method:
            summary_bullets.append(f"계약방식: {CONTRACT_METHOD_LABELS.get(slots.contract_method, slots.contract_method)}")
            
        if summary_bullets:
            sections.append(AnswerSection(title="계약 검토 요약", content="아래 조건을 기준으로 계약 유형 및 절차를 검토합니다.", bullets=summary_bullets))

    route_sec = None
    if "procurement_route_review" in all_intents:
        route_name = router_result.slots.procurement_route or "조달경로"
        route_sec = _route_review_section_obj(route_name)
        sections.append(route_sec)

    local_sec = None
    if "local_purchase_support" in all_intents:
        local_sec = _local_support_section()
        sections.append(local_sec)

    if "candidate_search" in all_intents:
        sections.append(AnswerSection(
            title="업체 후보 조회",
            content="현재는 업체 후보 조회 API 연동 전이므로 실제 후보 목록은 표시하지 않습니다.",
            bullets=["(Company API 연동 예정)"]
        ))

    item_sec = None
    if "item_eligibility" in all_intents:
        item_sec = _item_eligibility_section_obj()
        sections.append(item_sec)

    if router_result.clarification_needed:
        sections.append(AnswerSection(
            title="추가 확인 필요",
            content="정확한 안내를 위해 아래 정보가 추가로 필요합니다.",
            bullets=router_result.clarification_needed
        ))

    sections.append(_caution_section())

    return _build_output(
        sections, DISCLAIMER,
        local_purchase_support_review_section=local_sec,
        route_review_section=route_sec,
        item_eligibility_section=item_sec
    )


def build_out_of_scope(router_result: RouterResult) -> AnswerBuilderOutput:
    sections = [
        AnswerSection(title="안내", content="해당 질의는 시스템 지원 범위 밖입니다."),
        _caution_section()
    ]
    return _build_output(sections, DISCLAIMER)


def build_clarification(router_result: RouterResult) -> AnswerBuilderOutput:
    sections = [
        AnswerSection(
            title="추가 정보 요청",
            content="정확한 안내를 위해 아래 정보를 추가로 알려주시기 바랍니다.",
            bullets=router_result.clarification_needed if router_result.clarification_needed else ["질문을 더 구체적으로 입력해 주세요."]
        ),
        _caution_section()
    ]
    return _build_output(sections, DISCLAIMER)


# ─────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────

FLOW_MAP = {
    "legal_explanation_flow": build_legal_explanation,
    "contract_review_flow": build_contract_review,
    "local_purchase_support_flow": build_contract_review,
    "candidate_search_flow": build_candidate_search,
    "item_eligibility_flow": build_contract_review,
    "procurement_route_review_flow": build_legal_explanation,
    "mixed_flow": build_mixed_flow,
    "out_of_scope": build_out_of_scope,
    "clarification_required": build_clarification,
}

def route_answer(router_result: RouterResult, evidence_context=None, item_eligibility_context=None) -> AnswerBuilderOutput:
    """RouterResult.routing_decision에 따라 적절한 빌더를 호출한다.

    evidence_context가 전달되면 evidence section을 답변에 추가한다.
    item_eligibility_context가 전달되면 품목 적격성 판단 section을 추가한다.
    """
    builder_fn = FLOW_MAP.get(router_result.routing_decision, build_out_of_scope)
    out = builder_fn(router_result)

    if evidence_context is not None or item_eligibility_context is not None:
        from app.answer_builder.evidence_answer_builder import apply_evidence_to_answer
        out = apply_evidence_to_answer(out, evidence_context, item_eligibility_context=item_eligibility_context, router_slots=router_result.slots)

    return out

