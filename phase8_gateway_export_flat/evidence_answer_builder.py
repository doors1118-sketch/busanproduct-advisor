"""
Phase 10.5: Evidence Answer Builder

EvidenceContext를 받아 AnswerBuilderOutput에 evidence section을 추가하거나
기존 section을 보강한다.
"""
from typing import List

from app.answer_builder.schema import AnswerSection, AnswerBuilderOutput
from app.answer_builder.evidence_schema import EvidenceContext, RuleEvidenceStatus
from app.answer_builder.answer_type_router import FORBIDDEN_PHRASES

# unresolved 상태에서 출력 금지 수치 패턴
FORBIDDEN_NUMERIC_HINTS = [
    "5천만원", "50,000,000", "50000000",
    "1억원", "100,000,000", "100000000",
    "7.5점",
    "40%", "49%", "30%",
]

_DISPLAY_LEVEL_LABELS = {
    "source_verified": "검증된 source 후보가 확인되었습니다.",
    "source_candidate": "source 후보가 있으나 검토 상태 확인이 필요합니다.",
    "partial_evidence": "일부 근거 후보가 있으나 미매핑 항목 또는 수치 확인이 남아 있습니다.",
    "source_missing": "현재 source map 기준으로 직접 근거가 확인되지 않았습니다. 원문 확인이 필요합니다.",
    "company_api_only": "법령 source가 아니라 업체 후보 조회 API 연동 대상입니다.",
}


def build_evidence_sections(evidence_context: EvidenceContext) -> List[AnswerSection]:
    """EvidenceContext로부터 근거 기반 검토 상태 섹션 목록을 생성한다."""
    sections: List[AnswerSection] = []

    if not evidence_context.rule_statuses:
        return sections

    items = []
    for rs in evidence_context.rule_statuses:
        label = _DISPLAY_LEVEL_LABELS.get(rs.display_level, "검토 필요")
        line = f"- {rs.display_name}: {label}"

        # unresolved numeric이 있으면 수치 관련 안내 추가
        unresolved = [p for p in rs.numeric_parameters if not p.display_allowed]
        if unresolved:
            line += " (수치 기준은 최신 법령 원문 확인 필요)"

        items.append(line)

    content = "\n".join(items)
    sections.append(AnswerSection(title="근거 기반 검토 상태", content=content))

    # source gap 안내
    if evidence_context.source_gap_exists:
        sections.append(AnswerSection(
            title="Source Gap 안내",
            content="일부 검토 항목의 법령 source가 아직 완전히 매핑되지 않았습니다. "
                    "해당 항목은 '확인 필요'로 표시되었으며, 원문 대조가 권장됩니다."
        ))

    return sections


def _sanitize_evidence_text(text: str) -> str:
    """evidence 텍스트에서 금지 표현 및 unresolved 수치를 제거."""
    for phrase in FORBIDDEN_PHRASES:
        text = text.replace(phrase, "[표현 제한]")
    for hint in FORBIDDEN_NUMERIC_HINTS:
        text = text.replace(hint, "[수치 확인 필요]")
    return text


def apply_evidence_to_answer(
    answer_output: AnswerBuilderOutput,
    evidence_context: EvidenceContext
) -> AnswerBuilderOutput:
    """기존 AnswerBuilderOutput에 evidence sections를 추가한다."""
    evidence_sections = build_evidence_sections(evidence_context)

    if not evidence_sections:
        return answer_output

    # evidence section markdown 생성
    evidence_md_parts = []
    for sec in evidence_sections:
        sanitized = _sanitize_evidence_text(sec.content)
        evidence_md_parts.append(f"\n\n## {sec.title}\n{sanitized}")

    evidence_md = "\n".join(evidence_md_parts)

    # 주의사항 앞에 삽입
    caution_marker = "\n\n## 주의사항"
    if caution_marker in answer_output.rendered_markdown:
        answer_output.rendered_markdown = answer_output.rendered_markdown.replace(
            caution_marker,
            evidence_md + caution_marker
        )
    else:
        answer_output.rendered_markdown += evidence_md

    # 최종 forbidden phrase 재검사 (전체 markdown)
    # 주의: FORBIDDEN_NUMERIC_HINTS는 evidence section에만 적용하고
    # 기존 answer body에는 적용하지 않는다.
    # 사용자가 입력한 금액(예: 추정가격: 50,000,000원)이 치환되면 안 된다.
    final_md = answer_output.rendered_markdown
    for phrase in FORBIDDEN_PHRASES:
        if phrase in final_md:
            final_md = final_md.replace(phrase, "[표현 제한]")
    answer_output.rendered_markdown = final_md

    # scan metadata 갱신: route_answer 단독 호출 시에도 정확하게 유지
    blocked = [p for p in FORBIDDEN_PHRASES if p in answer_output.rendered_markdown]
    answer_output.blocked_phrases_found = blocked
    answer_output.forbidden_phrase_scan_passed = len(blocked) == 0

    return answer_output

