"""
Practical answer templates for public procurement guidance.

These templates keep fast deterministic answers readable without adding
another LLM rewrite call.
"""
import re

try:
    from .numeric_basis_policy import get_numeric_display, get_numeric_value
except ImportError:
    from policies.numeric_basis_policy import get_numeric_display, get_numeric_value


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


def _num(parameter_ref: str, fallback: str = "최신 기준 확인 필요") -> str:
    return get_numeric_display(parameter_ref) or fallback


def _is_it_equipment_item(item_label: str) -> bool:
    item = re.sub(r"\s+", "", item_label or "").lower()
    return any(term in item for term in ("컴퓨터", "노트북", "전산", "서버", "태블릿", "pc"))


def _amount_over(amount_value: int | None, parameter_ref: str) -> bool | None:
    threshold = get_numeric_value(parameter_ref)
    if amount_value is None or threshold is None:
        return None
    return amount_value > threshold


def _immediate_execution_priority_lines(
    contract_object: str | None,
    item_label: str,
    amount_label: str,
    amount_value: int | None,
) -> list[str]:
    """Summarize the practical first clicks before the longer route table."""
    if (contract_object or "goods").lower() != "goods":
        return []

    general_one_quote = _num("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
    policy_one_quote = _num("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD")
    mas_general = _num("P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD")
    mas_sme = _num("P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD")

    if _is_it_equipment_item(item_label):
        first_action = (
            f"나라장터 종합쇼핑몰에서 `{item_label}` 세부품명을 검색하고, "
            "`공급업체 소재지: 부산광역시`, 납품지역, 인도조건, 계약상태를 먼저 거릅니다."
        )
        first_basis = (
            f"{item_label} 세부품명이 중소기업자간 경쟁제품으로 확인되면 "
            f"MAS 2단계경쟁 기준({mas_sme}) 미만 여부를 먼저 봅니다. "
            f"일반 물품 기준({mas_general})과 다를 수 있으므로 세부품명 확인이 출발점입니다."
        )
        first_check = "SMPP 직접생산확인, 종합쇼핑몰/MAS 등록상품명, 부산 공급업체와 실제 납품 주체 일치 여부"
    else:
        first_action = (
            f"나라장터 종합쇼핑몰 또는 조달등록 자료에서 `{item_label}` 세부품명과 부산 공급 가능 업체를 먼저 확인합니다."
        )
        first_basis = (
            f"MAS 등록 품목이면 2단계경쟁 기준({mas_general} 또는 중기경쟁제품 {mas_sme})을 확인한 뒤 직접구매 가능성을 봅니다."
        )
        first_check = "세부품명, 쇼핑몰 계약상태, 공급업체 소재지, 납품 가능 지역"

    policy_over = _amount_over(amount_value, "P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD")
    general_over = _amount_over(amount_value, "P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
    if policy_over is True:
        one_quote_basis = f"질문 금액은 정책기업 1인견적 기준({policy_one_quote})을 초과하므로 1인 견적은 우선 제외합니다."
    elif general_over is True:
        one_quote_basis = (
            f"일반 1인견적 기준({general_one_quote})은 초과하므로, 정책기업 기준({policy_one_quote}) 등 별도 사유가 맞는지 확인합니다."
        )
    else:
        one_quote_basis = f"1인견적 가능성은 일반 기준({general_one_quote})과 정책기업 기준({policy_one_quote})을 나누어 확인합니다."

    return [
        "### 바로 실행 우선순위",
        f"- 내부 품의서에는 **총액({amount_label})**, 추정가격(VAT 별도), 세부품명, 조달 경로, 부산업체 검토 근거를 분리해서 적으세요.",
        "",
        "| 순서 | 지금 할 일 | 내부 근거에 쓸 논리 | 확인할 것 |",
        "|---|---|---|---|",
        f"| 1 | {first_action} | {first_basis} | {first_check} |",
        f"| 2 | 원하는 규격의 부산 쇼핑몰 제품이 없거나 직접구매가 부적절하면 G2B 2인 이상 견적 또는 지역제한 가능성을 검토합니다. | {one_quote_basis} 경쟁성 있는 견적 절차로 전환하면 특정업체 지정 리스크를 줄일 수 있습니다. | 견적공고 가능 금액, 부산 지역제한 가능 여부, 경쟁 가능한 부산업체 수 |",
        "| 3 | 후보 업체는 쇼핑몰 등록, 조달등록, 정책기업, 기술개발제품 여부를 한 표에서 비교합니다. | 부산업체 지원은 소재지만으로 결정하지 않고, 조달 경로와 품목 적격성을 충족하는 업체를 우선 검토했다는 근거를 남깁니다. | 등록상품명, 직접생산확인, 인증 유효성, 납품·A/S 조건 |",
        "",
    ]


def _local_purchase_strategy_lines(contract_object: str | None, item_label: str, amount_label: str) -> list[str]:
    object_key = (contract_object or "goods").lower()
    general_one_quote = _num("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
    policy_one_quote = _num("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD")
    mas_general = _num("P_MAS_SECOND_STAGE_GENERAL_PRODUCT_THRESHOLD")
    mas_sme = _num("P_MAS_SECOND_STAGE_SME_COMPETITION_THRESHOLD")
    local_goods_service = _num("P_LOCAL_LIMITED_BID_GOODS_SERVICE_NOTICE_THRESHOLD")

    if object_key == "goods":
        return [
            "- **우선순위는 고정하지 않습니다.** 금액, 세부품명, 종합쇼핑몰 등록 여부, 중소기업자간 경쟁제품 여부, 정책기업/인증제품 해당 여부, 부산 후보 존재 여부를 같이 보아 경로를 정합니다.",
            "",
            "| 상황 | 먼저 볼 경로 | 부산업체 수주 지원 방법 | 확인 근거 |",
            "|---|---|---|---|",
            f"| MAS 등록 품목이고 2단계 경쟁 기준 미만 | 종합쇼핑몰/MAS 납품요구 또는 직접구매 | 공급업체 소재지, 납품지역, 인도조건, A/S 조건에서 부산 후보를 비교 | 물품 다수공급자계약 업무처리규정, 2단계경쟁 업무처리기준. 일반 제품 기준 {mas_general}, 중기경쟁제품 기준 {mas_sme} |",
            "| MAS 2단계 경쟁 대상이거나 직접구매가 부적절 | MAS 2단계 경쟁 또는 자체 경쟁 절차 | 납기, 사후관리, 현장지원, 지역 서비스망처럼 품목 수행과 직접 관련된 평가요소로 반영 | 종합쇼핑몰 운영규정, 물품 다수공급자계약 2단계경쟁 업무처리기준 |",
            f"| 소액수의 금액대이고 법정 사유가 맞음 | 일반 1인 견적 또는 정책기업 1인 견적 | 부산 소재 정책기업·인증기업을 후보로 검토하되 금액·사유 충족 시에만 적용 | 지방계약법 시행령 제25조·제30조. 일반 1인 견적 기준 {general_one_quote}, 정책기업 기준 {policy_one_quote} |",
            f"| 1인 견적 한도 초과 또는 특정업체 지정 곤란 | 2인 이상 견적, 지역제한 가능성 검토 | G2B 견적공고·입찰에서 부산 지역제한 가능 여부와 경쟁 가능한 업체 수를 확인 | 지방계약법 시행규칙 제24조, 지방자치단체 입찰 및 계약집행기준. 물품·일반용역 지역제한 기준 {local_goods_service} |",
            "| 기술개발·우수조달·혁신제품 후보가 품목과 일치 | 우선구매 또는 수의계약 특례 검토 | 부산업체 제품이라도 인증명·지정상태·구매품목 일치가 확인될 때만 별도 경로로 검토 | 중소기업제품 구매촉진법령, 우수조달물품·혁신제품 관련 규정 |",
        ]

    if object_key == "service":
        return [
            "- **우선순위는 금액과 과업 성격에 따라 바뀝니다.** 용역은 종합쇼핑몰보다 지역제한, 2인 이상 견적, 협상계약 평가항목, 공동수급 설계가 더 중요할 수 있습니다.",
            "",
            "| 상황 | 먼저 볼 경로 | 부산업체 수주 지원 방법 | 확인 근거 |",
            "|---|---|---|---|",
            f"| 소액수의 금액대 | 1인 견적 또는 2인 이상 견적 | 부산 소재 수행업체·정책기업 후보를 검토하되 금액과 수의계약 사유를 먼저 확인 | 지방계약법 시행령 제25조·제30조. 일반 1인 견적 기준 {general_one_quote}, 정책기업 기준 {policy_one_quote} |",
            f"| 경쟁 절차가 필요한 일반 용역 | 지역제한 또는 지역업체 참여 평가 | 부산 지역제한 가능 금액과 경쟁 가능한 업체 수를 확인하고, 필요하면 지역업체 참여도·현장 대응성을 평가항목으로 설계 | 지방계약법 시행규칙 제24조, 지방자치단체 입찰시 낙찰자 결정기준. 물품·일반용역 지역제한 기준 {local_goods_service} |",
            "| 제안서 평가가 적합한 용역 | 협상에 의한 계약 | 지역 이해도, 현장 운영능력, 민원·안전 대응, 지역 협력망을 정당한 평가항목으로 반영 | 지방자치단체 입찰시 낙찰자 결정기준, 협상계약 평가기준 |",
            "| 대형·복합 용역 | 공동수급·분담이행 검토 | 전국 업체 참여가 불가피하면 부산업체 공동수급 비율 또는 지역 수행분담을 유도 | 공동계약 관련 예규, 기관별 입찰공고 기준 |",
        ]

    if object_key == "construction":
        return [
            "- **우선순위는 공종과 금액이 먼저 결정합니다.** 공사는 수의계약 한도, 지역제한, 지역의무공동도급, 지역업체 참여도 평가를 분리해서 봐야 합니다.",
            "",
            "| 상황 | 먼저 볼 경로 | 부산업체 수주 지원 방법 | 확인 근거 |",
            "|---|---|---|---|",
            "| 공종별 수의계약 한도 이내 | 공사 수의계약 가능성 검토 | 부산 소재 면허업체를 후보로 보되 공종·금액·수의계약 사유를 먼저 확인 | 지방계약법 시행령 제25조·제30조, 수의계약 운영요령 |",
            "| 지역제한 가능 금액대 | 부산 지역제한 입찰 | 본점 소재지, 면허, 경쟁 가능한 업체 수를 확인해 부당제한 위험을 줄임 | 지방계약법 시행규칙 제24조 |",
            "| 지역제한만으로 부족하거나 대형 공사 | 지역의무공동도급·공동수급 | 부산업체 지분율, 분담공종, 지역업체 참여도 평가를 함께 설계 | 공동계약 관련 예규, 지방자치단체 입찰시 낙찰자 결정기준 |",
        ]

    return [
        "- **우선순위는 고정하지 않습니다.** 계약대상, 금액, 적용 법령, 후보 업체 존재 여부를 확인한 뒤 가능한 경로를 좁히세요.",
    ]


def _item_trait_checkpoints(item_label: str, contract_object: str | None) -> list[str]:
    item = re.sub(r"\s+", "", item_label or "").lower()
    object_key = (contract_object or "goods").lower()
    lines: list[str] = []

    if object_key == "goods":
        lines.extend([
            "- **납품·설치·검수 범위**: 단순 납품인지, 현장설치도·철거·시운전·사용자 교육·하자보수가 포함되는지 계약조건에 분리해서 적으세요.",
            "- **유지보수/A/S 대응성**: 고장 대응, 부품 수급, 현장 출동, 서비스센터 또는 협력망은 특정 지역업체 지정이 아니라 품목 수행과 직접 관련된 평가요소로 설계하세요.",
            "- **부대 공사·면허 확인**: 전기·통신·소방·건설공사가 함께 들어가면 물품 구매로만 처리할 수 있는지, 별도 공사 또는 면허 요건이 필요한지 확인하세요.",
        ])
        if any(term in item for term in ("냉난방", "에어컨", "공기조화", "공조", "히트펌프", "보일러", "냉동기")):
            lines.extend([
                "- **설비성 물품 체크**: 실외기 위치, 배관·배수, 기존 장비 철거, 전기 용량·분전반, 소음·안전 기준을 현장 확인사항에 넣으세요.",
                "- **에너지 기준**: 에너지소비효율등급, 고효율 에너지기자재, 녹색제품 등 공공구매 의무·우선구매 대상 여부를 확인하세요.",
            ])
        elif any(term in item for term in ("cctv", "영상감시", "카메라", "서버", "소프트웨어", "전산", "네트워크", "컴퓨터", "노트북")):
            lines.extend([
                "- **기술지원·보안 조건**: 라이선스, 유지보수 기간, 기술지원확약, 보안·호환성 요건이 특정 제조사 맞춤 조건이 되지 않도록 검토하세요.",
                "- **세부품명·직접생산**: 전산장비는 세부품명, 직접생산확인, 중소기업자간 경쟁제품 여부에 따라 후보 적격성이 달라질 수 있습니다.",
            ])
        else:
            lines.append(
                "- **품목별 특수조건**: 안전인증, 성능시험, 에너지·환경 기준, 설치 조건, 유지관리 조건 중 해당 품목에 필요한 항목을 공고 전 시장조사에서 확인하세요."
            )

    return lines


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
    amount_value: int | None = None,
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
    ]
    parts.extend(_immediate_execution_priority_lines(contract_object, item_label, amount_label, amount_value))
    parts.extend(
        [
            "### 1. 계약방법 및 구매 경로 검토",
            _clean_part(route_guidance)
            or "- 금액 기준, 품목 특성, 조달등록·종합쇼핑몰 등록 여부를 관련 법령·행정규칙 근거와 함께 확인하세요.",
            "",
            "### 2. 부산 지역업체 구매 확대 전략",
        ]
    )
    parts.extend(_local_purchase_strategy_lines(contract_object, item_label, amount_label))

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
    parts.extend(_item_trait_checkpoints(item_label, contract_object))

    references = [_clean_part(practice_manual_text), _clean_part(pps_qa_text)]
    references = [text for text in references if text]
    if references:
        parts.extend(["", "### 5. 참고 근거"])
        parts.extend(_demote_markdown_headings(text) for text in references)

    parts.append("")
    parts.append("- 이 답변은 확인된 법령·행정규칙 자료와 업체 후보 자료를 조합한 실무 검토용 안내입니다. 실제 계약 전에는 최신 법령·행정규칙과 기관 내부 기준을 확인하세요.")
    return parts
