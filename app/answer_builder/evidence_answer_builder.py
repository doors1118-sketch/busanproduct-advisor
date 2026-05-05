"""
Phase 10.5: Evidence Answer Builder

EvidenceContext를 받아 AnswerBuilderOutput에 evidence section을 추가하거나
기존 section을 보강한다.
"""
from typing import List
import os
import json
from pathlib import Path

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

PARAMETER_LABELS = {
    "P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD": "일반 물품·용역 수의계약 기준",
    "P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD": "일반 1인 견적 기준",
    "P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD": "정책기업 1인 견적 기준",
    "P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD": "소기업·소상공인 등 수의계약 기준",
    "P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD": "정책기업 수의계약 기준",
}

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
    
    current_file = Path(__file__).resolve()
    search_dirs = [
        current_file.parent,
        current_file.parent.parent,
        current_file.parents[2],
        current_file.parents[2] / "app" / "data"
    ]
    
    article_db = {}
    for base_dir in search_dirs:
        path = base_dir / "key_articles.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                article_db = json.load(f)
            break

    if not evidence_context.rule_statuses:
        return sections

    items = []
    for rs in evidence_context.rule_statuses:
        label = _DISPLAY_LEVEL_LABELS.get(rs.display_level, "검토 필요")
        line = f"- {rs.display_name}: {label}"

        # unresolved numeric이 있으면 수치 관련 안내 추가
        has_unresolved_numeric = any(not p.display_allowed for p in rs.numeric_parameters)
        if has_unresolved_numeric:
            line += " (수치 기준은 최신 법령 원문 확인 필요)"

        # 개별 라인에 대해서만 sanitize를 수행하거나, 여기서 처리하지 않고 나중에 분리.
        # AnswerBuilder 로직에서 일괄 sanitize를 방지하기 위해 특수 토큰을 사용하거나,
        # 원문을 AnswerSection의 추가 속성으로 빼거나, 아니면 여기에서 치환되지 않도록 분리합니다.
        # 일단은 텍스트 분리를 위해 원문 블록은 items 배열이 아닌 별도 변수에 모아둔 뒤 붙입니다.
        sanitized_line = _sanitize_evidence_text(line)
        items.append(sanitized_line)
        
        # source_verified 이고 원문 DB에 있으면 원문 추가
        # 단, unresolved numeric이 있다면 원문에 수치가 섞여 있을 수 있으므로 출력을 차단한다.
        if not has_unresolved_numeric and rs.display_level in ("source_verified", "partial_evidence") and rs.rule_id in article_db:
            text_snippet = article_db[rs.rule_id]
            if len(text_snippet) > 200:
                text_snippet = text_snippet[:200] + "...\n(이하 생략: 너무 긴 원문은 가독성을 위해 축약되었습니다)"
                
            # UI 개선: <details> 태그를 이용해 긴 원문 접기
            raw_article_block = (
                f"\n<details>\n<summary><b>{rs.display_name} 관련 조문 발췌 보기</b></summary>\n"
                f"\n> " + text_snippet.replace("\n", "\n> ") + "\n</details>\n"
            )
            # 이 블록은 sanitize 되지 않아야 하므로 임시 리스트에 추가
            items.append(raw_article_block)

    # Threshold 정보가 있으면 상단에 명시적으로 추가
    if getattr(evidence_context, "threshold_value_used", None) is not None and getattr(evidence_context, "threshold_ref_used", None) is not None:
        val = evidence_context.threshold_value_used
        ref = evidence_context.threshold_ref_used
        
        # 권한 교차 검증: rule_statuses 내부의 해당 파라미터가 display_allowed == True 인지 확인
        is_display_allowed = False
        for rs in evidence_context.rule_statuses:
            for p in rs.numeric_parameters:
                if p.parameter_ref == ref:
                    if p.display_allowed:
                        is_display_allowed = True
                    break
            if is_display_allowed:
                break
                
        if is_display_allowed and ref in PARAMETER_LABELS:
            label = PARAMETER_LABELS[ref]
            # 수치 마스킹을 피하기 위해 포맷팅 (answer_output에 추가될 때는 FORBIDDEN_NUMERIC_HINTS 안 걸림)
            formatted_val = f"{val:,}원"
            threshold_info = f"\n> [!NOTE]\n> **적용 기준**: {label}\n> **기준 금액**: {formatted_val}\n"
            items.insert(0, threshold_info)

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
    evidence_context: EvidenceContext,
    item_eligibility_context=None
) -> AnswerBuilderOutput:
    """기존 AnswerBuilderOutput에 evidence sections를 추가한다."""
    evidence_sections = build_evidence_sections(evidence_context) if evidence_context else []
    
    if item_eligibility_context:
        item_name = item_eligibility_context.detail_item_name or "알 수 없음"
        
        status = item_eligibility_context.eligibility_status
        if status == "data_unavailable":
            detail_item_code = "품목 적격성 DB 조회 불가"
        elif status == "not_found":
            detail_item_code = "매칭 품목 없음"
        elif status == "ambiguous":
            detail_item_code = "후보 품목 다수로 확정 불가"
        else:
            detail_item_code = item_eligibility_context.detail_item_code or "알 수 없음"
        
        is_sme = "해당" if item_eligibility_context.is_sme_competition_product else "해당 없음"
        if item_eligibility_context.is_sme_competition_product is None:
            is_sme = "세부품명번호 확정 후 확인 필요"
            
        is_dp = "대상" if item_eligibility_context.direct_production_required else "대상 아님"
        if item_eligibility_context.direct_production_required is None:
            is_dp = "세부품명번호 확정 후 확인 필요"
            
        cert_status = item_eligibility_context.company_cert_status or "특정 업체가 제시되지 않아 확인하지 않음"
        if cert_status == "not_found":
            cert_status = "인증 정보 없음 (또는 미보유)"
        elif cert_status == "expired":
            cert_status = "인증 만료"
        elif cert_status == "verified":
            cert_status = "인증 유효"
            
        content_lines = [
            f"- 품목명: {item_name}",
            f"- 세부품명번호: {detail_item_code}"
        ]
        
        if status == "ambiguous" and item_eligibility_context.candidate_items:
            content_lines.append("  - **후보 목록:**")
            for i, cand in enumerate(item_eligibility_context.candidate_items[:5]): # 최대 5개
                content_lines.append(f"    - 후보 {i+1}: {cand.get('detail_item_name', '')} / {cand.get('detail_item_code', '')}")

        content_lines.extend([
            f"- 중소기업자간 경쟁제품 여부: {is_sme}",
            f"- 직접생산확인 대상 여부: {is_dp}",
            f"- 업체 인증 상태: {cert_status}"
        ])
        
        content = "\n".join(content_lines)
        from app.answer_builder.schema import AnswerSection
        evidence_sections.insert(0, AnswerSection(title="품목 적격성 검토", content=content))

    if not evidence_sections:
        return answer_output

    # evidence section markdown 생성
    evidence_md_parts = []
    for sec in evidence_sections:
        # sec.content는 이미 build_evidence_sections 안에서 개별 라인별로 sanitize 되었습니다.
        # 단, source_gap 안내 등은 여기서 sanitize 될 필요가 없으나 안전하게 통과됩니다.
        # 따라서 전체 일괄 sanitize는 제거합니다.
        evidence_md_parts.append(f"\n\n## {sec.title}\n{sec.content}")

    evidence_md = "\n".join(evidence_md_parts)

    # 1차 forbidden phrase scan (evidence 섹션 추가 전 원본 + evidence)
    from app.answer_builder.answer_type_router import FORBIDDEN_PHRASES
    pre_blocked = [p for p in FORBIDDEN_PHRASES if p in evidence_md]
    if pre_blocked:
        existing_blocked = set(answer_output.blocked_phrases_found)
        existing_blocked.update(pre_blocked)
        answer_output.blocked_phrases_found = list(existing_blocked)
        answer_output.forbidden_phrase_scan_passed = False

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

    # scan metadata 갱신: 기존에 발견된 blocked가 있다면 보존
    blocked = [p for p in FORBIDDEN_PHRASES if p in answer_output.rendered_markdown]
    if blocked:
        # 중복 제거 후 병합
        existing_blocked = set(answer_output.blocked_phrases_found)
        existing_blocked.update(blocked)
        answer_output.blocked_phrases_found = list(existing_blocked)
        answer_output.forbidden_phrase_scan_passed = False

    return answer_output

