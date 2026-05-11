"""
Practical answer templates for public procurement guidance.

These templates keep fast deterministic answers readable without adding
another LLM rewrite call.
"""
import re


def _clean_part(text: str | None) -> str:
    return str(text or "").strip()


def _demote_markdown_headings(text: str) -> str:
    return re.sub(r"(?m)^###\s+", "#### ", text)


def _object_label(contract_object: str | None) -> str:
    return {
        "goods": "물품",
        "service": "용역",
        "construction": "공사",
    }.get((contract_object or "goods").lower(), "계약")


def build_multi_route_practical_answer_parts(
    *,
    amount_label: str,
    item_label: str,
    contract_object: str | None = "goods",
    route_guidance: str = "",
    catalog_guidance: str = "",
    practice_manual_text: str = "",
    pps_qa_text: str = "",
    candidate_table_text: str = "",
    candidate_export_row_count: int = 0,
    policy_company_sections_skipped: bool = False,
) -> list[str]:
    """Build a natural, reusable answer structure for purchase-route guidance."""
    amount_label = amount_label or "금액 미확인"
    item_label = item_label or "구매 대상"
    object_label = _object_label(contract_object)

    parts: list[str] = [
        f"### {amount_label} 규모 {item_label} 구매 실무 가이드",
        (
            f"현재 조건은 **{amount_label} 규모의 {item_label} {object_label} 검토**입니다. "
            "일반 수의계약 여부만 단정하기보다, 금액 기준·품목 특성·조달 경로·지역업체 활용 가능성을 함께 보는 방식이 안전합니다."
        ),
        "",
        "### 1. 계약방법 및 구매 경로 검토",
        _clean_part(route_guidance)
        or "- 금액 기준, 품목 특성, 조달등록·종합쇼핑몰 등록 여부를 관련 법령·행정규칙 근거와 함께 확인하세요.",
        "",
        "### 2. 부산 지역업체 구매 확대 전략",
        "- **정책기업 1인 견적 검토**: 여성기업·장애인기업·사회적기업 등 정책기업 요건과 금액 기준이 맞으면 부산 소재 업체와의 1인 견적 가능성을 먼저 확인합니다.",
        "- **지역제한 검토**: 법령상 허용되는 금액·계약대상·경쟁성 범위에서 부산 소재 업체 제한 가능성을 검토합니다.",
        "- **종합쇼핑몰/MAS 활용**: 등록 상품이면 부산 소재 공급업체, 납품요구 가능 여부, 2단계 경쟁 대상 여부를 함께 확인합니다.",
        "- **중소기업자간 경쟁제품·직접생산확인**: 해당 품목이면 세부품명과 직접생산확인 범위를 후보 적격성의 핵심 확인사항으로 둡니다.",
        "- **인증제품 검토**: 기술개발제품·우수조달·혁신제품은 인증·지정 상태와 구매품목 일치가 확인될 때 우선구매 또는 수의계약 특례 검토군으로 봅니다.",
    ]

    catalog = _clean_part(catalog_guidance)
    if catalog:
        parts.extend(["", catalog])

    candidate = _clean_part(candidate_table_text)
    parts.extend(["", "### 3. 검토 대상 부산 지역업체 후보"])
    if candidate:
        parts.append(candidate)
        if policy_company_sections_skipped:
            parts.append(
                "- 정책기업 1인 견적 경로는 금액상 우선 제외됩니다. 여성기업ㆍ장애인기업ㆍ사회적기업 여부는 후보 업체의 추가 확인사항으로만 보세요."
            )
        if candidate_export_row_count:
            parts.append(
                f"- 화면에는 주요 후보만 표시했습니다. 전체 후보 {candidate_export_row_count}건은 답변 하단의 엑셀 다운로드로 확인하세요."
            )
    else:
        parts.append("- 현재 사전검색 결과에서 바로 표시할 업체 후보가 부족합니다. 품목명 또는 세부 규격을 더 구체화해 재검색하세요.")

    parts.extend(
        [
            "",
            "### 4. 실무자 필수 체크포인트",
            "- **세부품명 일치**: 후보 업체의 등록상품명·인증제품명·직접생산확인 범위가 실제 구매품목과 맞는지 확인하세요.",
            "- **계약방식 적정성**: 금액 기준, 1인 견적 가능 여부, 2인 이상 견적 필요 여부, MAS 2단계 경쟁 여부를 분리해서 확인하세요.",
            "- **분할발주 주의**: 금액 기준을 맞추기 위한 임의 분할은 감사 지적 위험이 있으므로 통합 발주 원칙에서 검토하세요.",
            "- **기관 내부 지침 확인**: 지역상품 구매 촉진 지침, 예산집행 기준, 조달 관련 내부 절차를 함께 확인하세요.",
        ]
    )

    references = [_clean_part(practice_manual_text), _clean_part(pps_qa_text)]
    references = [text for text in references if text]
    if references:
        parts.extend(["", "### 5. 참고 근거"])
        parts.extend(_demote_markdown_headings(text) for text in references)

    parts.append("")
    parts.append("- 이 답변은 확인된 법령·행정규칙 자료와 업체 후보 자료를 조합한 실무 검토용 안내입니다. 실제 계약 전에는 최신 법령·행정규칙과 기관 내부 기준을 확인하세요.")
    return parts
