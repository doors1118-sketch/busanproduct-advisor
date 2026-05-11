"""
Deterministic legal answer gate for high-frequency procurement standards.

These answers cover narrow, repeatedly asked 기준/정의/한도 questions where
free-form LLM generation tends to add noise or mix unrelated thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

try:
    from policies.numeric_basis_policy import get_numeric_display, get_numeric_value
except ImportError:
    from importlib import import_module

    _numeric_basis_policy = import_module("app.policies.numeric_basis_policy")
    get_numeric_display = _numeric_basis_policy.get_numeric_display
    get_numeric_value = _numeric_basis_policy.get_numeric_value


@dataclass(frozen=True)
class DeterministicLegalAnswer:
    answer: str
    reason: str
    schema_version: str


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


def _item_hint(text: str) -> str:
    for term in (
        "냉난방기", "보안용카메라", "CCTV", "노트북", "컴퓨터", "프린터",
        "서버", "LED조명", "LED", "사무가구", "가구",
    ):
        if term.lower() in (text or "").lower():
            return "LED 조명" if term == "LED" else term
    return ""


def _num(parameter_ref: str, fallback: str = "기준값 확인 필요") -> str:
    return get_numeric_display(parameter_ref) or fallback


def _money_limit(parameter_ref: str, suffix: str = " 이하") -> str:
    display = get_numeric_display(parameter_ref)
    return f"{display}{suffix}" if display else "기준값 확인 필요"


def _regional_amount_line(agency: str, parameter_ref: str, basis: str) -> list[str]:
    amount = _money_limit(parameter_ref, " 미만")
    return [
        f"- **{agency}**: **{amount}**",
        f"  근거: {basis}",
    ]


def match_deterministic_legal_answer(user_message: str) -> DeterministicLegalAnswer | None:
    q = _compact(user_message)

    if _is_agency_law_conflict(q):
        return None

    if _is_policy_company_product_counted_as_sme_performance(q):
        return DeterministicLegalAnswer(
            answer=_policy_company_product_counted_as_sme_performance_answer(),
            reason="policy_company_product_counted_as_sme_performance_fast_answer",
            schema_version="policy_company_product_counted_as_sme_performance_v1",
        )

    if _is_sme_small_business_priority_procurement(q):
        return DeterministicLegalAnswer(
            answer=_sme_small_business_priority_procurement_answer(),
            reason="sme_small_business_priority_procurement_fast_answer",
            schema_version="sme_small_business_priority_procurement_v1",
        )

    if _is_innovation_product_purchase_review(q):
        return DeterministicLegalAnswer(
            answer=_innovation_product_purchase_review_answer(),
            reason="innovation_product_purchase_fast_answer",
            schema_version="innovation_product_purchase_v1",
        )

    if _is_public_corp_direct_contract_difference(q):
        return DeterministicLegalAnswer(
            answer=_public_corp_direct_contract_difference_answer(),
            reason="public_corp_direct_contract_difference_fast_answer",
            schema_version="public_corp_direct_contract_difference_v1",
        )

    if _is_construction_repair_direct_limit_question(q):
        return DeterministicLegalAnswer(
            answer=_construction_repair_direct_limit_answer(),
            reason="construction_repair_direct_limit_fast_answer",
            schema_version="construction_repair_direct_limit_v1",
        )

    if _is_regional_restriction(q):
        return DeterministicLegalAnswer(
            answer=_regional_restriction_answer(q),
            reason="regional_restriction_standard_fast_answer",
            schema_version="regional_restriction_standard_v1",
        )

    if _is_sole_contract(q):
        return DeterministicLegalAnswer(
            answer=_sole_contract_answer(q),
            reason="sole_contract_standard_fast_answer",
            schema_version="sole_contract_standard_v1",
        )

    if _is_local_company_point(q):
        return DeterministicLegalAnswer(
            answer=_local_company_point_answer(q),
            reason="local_company_point_standard_fast_answer",
            schema_version="local_company_point_standard_v1",
        )

    if _is_excellent_procurement_or_third_party(q):
        return DeterministicLegalAnswer(
            answer=_excellent_procurement_or_third_party_answer(),
            reason="excellent_procurement_third_party_fast_answer",
            schema_version="excellent_procurement_third_party_v1",
        )

    if _is_split_purchase_audit_review(q):
        return DeterministicLegalAnswer(
            answer=_split_purchase_audit_review_answer(q),
            reason="split_purchase_audit_fast_answer",
            schema_version="split_purchase_audit_v1",
        )

    if _is_audit_risk_review(q):
        return DeterministicLegalAnswer(
            answer=_audit_risk_review_answer(),
            reason="audit_risk_fast_answer",
            schema_version="audit_risk_v1",
        )

    if _is_mas_regional_review(q):
        if _should_defer_mas_purchase_to_route_flow(q):
            return None
        return DeterministicLegalAnswer(
            answer=_mas_regional_review_answer(q),
            reason="mas_regional_review_fast_answer",
            schema_version="mas_regional_review_v1",
        )

    if _is_regional_mandatory_joint_contract(q):
        return DeterministicLegalAnswer(
            answer=_regional_mandatory_joint_contract_answer(q),
            reason="regional_mandatory_joint_contract_fast_answer",
            schema_version="regional_mandatory_joint_contract_v1",
        )

    return None


def _is_regional_restriction(q: str) -> bool:
    if not ("지역제한" in q or "지역제한경쟁" in q):
        return False
    if not any(term in q for term in ("기준", "금액", "얼마", "몇억", "100억", "150억", "88억", "비교")):
        return False
    if "종합공사" in q or "건설공사" in q:
        return True
    agency_compare = sum([
        "국가" in q,
        "공기업" in q or "준정부" in q or "공공기관" in q,
        "지방" in q or "지방자치단체" in q or "지자체" in q,
    ]) >= 2
    return agency_compare


def _is_agency_law_conflict(q: str) -> bool:
    has_national_or_public = any(term in q for term in ("국가기관", "국가계약", "공기업", "준정부", "공공기관"))
    has_local_law = any(term in q for term in ("지방계약", "지방자치단체", "지자체"))
    has_conflict_ask = any(term in q for term in (
        "그대로", "다르", "안되", "안되지", "혼동", "우대",
        "참고", "준용", "적용", "충돌", "차이",
    ))
    return has_national_or_public and has_local_law and has_conflict_ask


def _should_defer_mas_purchase_to_route_flow(q: str) -> bool:
    """품목 구매 실행 질문은 원칙답변보다 경로·후보 결합 플로우로 보낸다."""
    has_mas = any(term in q for term in ("종합쇼핑몰", "mas", "다수공급자", "나라장터", "제3자단가"))
    has_purchase_action = any(term in q for term in ("구매", "구입", "사면", "살수", "발주", "납품", "처리", "도입"))
    has_local_signal = any(term in q for term in ("부산", "지역업체", "부산업체", "관내업체", "지역상품", "부산상품"))
    has_execution_ask = any(term in q for term in ("가능", "방법", "어떻게", "고려", "안내", "처리", "검토", "해야"))
    return has_mas and has_purchase_action and has_local_signal and has_execution_ask


def _is_policy_company_product_counted_as_sme_performance(q: str) -> bool:
    has_policy_company = any(term in q for term in ("여성기업", "장애인기업", "여성기업제품", "장애인기업제품"))
    has_sme_performance = "중소기업제품" in q and any(term in q for term in ("구매실적", "실적", "구매목표", "목표비율"))
    asks_counting = any(term in q for term in ("포함", "인정", "잡히", "되는지", "되나요", "되나", "맞는지"))
    return has_policy_company and has_sme_performance and asks_counting


def _policy_company_product_counted_as_sme_performance_answer() -> str:
    return "\n".join([
        "네. **여성기업제품과 장애인기업제품 구매실적은 원칙적으로 중소기업제품 구매실적에도 포함해서 볼 수 있습니다.**",
        "",
        "### 1. 판단 요약",
        "- 여성기업제품, 장애인기업제품은 각각 별도의 의무구매 실적 항목으로 구분해 관리합니다.",
        "- 동시에 해당 기업유형 자체가 중소기업 범주를 전제로 하므로, 중소기업제품 총 구매실적에도 함께 반영되는 구조로 보는 것이 맞습니다.",
        "- 따라서 실무 입력에서는 `중소기업제품 총 실적`과 `여성기업제품/장애인기업제품 세부 실적`을 구분해 관리하되, 여성기업·장애인기업 구매액을 중소기업제품 총 실적에서 제외할 필요는 없습니다.",
        "",
        "### 2. 근거 축",
        "- **판로지원법 제5조**: 공공기관은 중소기업제품 구매계획과 전년도 구매실적을 작성·통보합니다.",
        "- **여성기업지원법 제9조**: 공공기관 우선구매 대상 여성기업은 `중소기업기본법 제2조에 따른 중소기업자`인 여성기업을 전제로 하고, 판로지원법상 구매계획에 여성기업제품 구매계획을 구분 포함합니다.",
        "- **장애인기업활동 촉진법 제2조 및 제9조의2**: 장애인기업은 중소기업 중 요건을 갖춘 기업이고, 장애인기업제품 구매계획도 판로지원법상 구매계획에 구분 포함합니다.",
        "",
        "### 3. 실무 확인사항",
        "- 구매일 기준 여성기업확인서 또는 장애인기업확인서가 유효한지 확인합니다.",
        "- 여성기업제품·장애인기업제품 실적으로 잡을 때는 해당 기업이 직접 생산·제공·수행하는 제품인지 확인합니다.",
        "- 중소기업제품 총실적, 여성기업제품 실적, 장애인기업제품 실적은 보고 항목이 다르므로 SMPP/공공구매종합정보망 입력 기준에 맞춰 구분 입력합니다.",
        "- 중증장애인생산품, 장애인표준사업장 생산품 등은 별도 제도와 겹칠 수 있으므로 해당 항목은 별도 실적 기준도 함께 확인합니다.",
        "",
        "정리하면, **중소기업제품 실적에는 포함하고, 여성기업제품·장애인기업제품 실적에도 별도로 구분 관리**하는 방식이 실무적으로 맞습니다.",
        "⚖️ 본 답변은 내부 법령 DB와 매뉴얼 기준의 참고 안내입니다. 실적 입력 전에는 해당 연도 공공구매종합정보망 입력 지침을 함께 확인하세요.",
    ])


def _is_sme_small_business_priority_procurement(q: str) -> bool:
    has_sme_competition = any(term in q for term in ("중소기업자간", "중기간", "경쟁제품"))
    has_small_business = "소기업" in q or "소상공인" in q
    has_small_amount = any(term in q for term in ("1억원미만", "1억미만", "일억원미만"))
    amount = _extract_amount_won(q)
    threshold = get_numeric_value("P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD")
    if amount is not None and isinstance(threshold, (int, float)) and amount < threshold:
        has_small_amount = True
    asks_limit = any(term in q for term in ("입찰참가자격", "제한", "맞", "해야", "원칙", "우선조달"))
    return has_sme_competition and has_small_business and has_small_amount and asks_limit


def _sme_small_business_priority_procurement_answer() -> str:
    threshold = _num("P_LOCAL_DIRECT_SMALL_BUSINESS_THRESHOLD")
    return "\n".join([
        f"네. 질문 조건처럼 **중소기업자간 경쟁제품**이고 추정가격이 **{threshold} 미만**인 물품·용역이라면, 먼저 **소기업 또는 소상공인 간 제한경쟁입찰** 적용 여부를 검토하는 구조가 맞습니다.",
        "",
        "### 1. 판단 요약",
        f"- 중소기업자간 경쟁제품이라는 점만으로 곧바로 `중소기업자 전체`로 넓히기보다, 추정가격이 {threshold} 미만이면 판로지원법 시행령의 **소기업·소상공인 우선조달계약** 기준을 먼저 봅니다.",
        "- 다만 품목의 세부품명, 직접생산확인 대상 여부, 유찰·긴급 등 예외 사유가 있는지는 별도 확인해야 합니다.",
        "",
        "### 2. 근거 축",
        f"- **중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령 제2조의2**: 추정가격 {threshold} 미만 물품 또는 용역은 소기업 또는 소상공인 간 제한경쟁입찰로 조달계약을 체결하는 구조를 둡니다.",
        "- **중소기업제품 구매촉진 및 판로지원에 관한 법률 제7조**: 경쟁제품은 중소기업자만을 대상으로 하는 제한경쟁 또는 지명경쟁 입찰로 조달하는 원칙을 둡니다.",
        "- **지방계약법 시행령 제20조**: 중소기업자간 경쟁제품, 소기업·소상공인 등 입찰참가자격 제한의 계약법상 연결 근거를 확인합니다.",
        "",
        "### 3. 실무 처리 순서",
        "- 먼저 세부품명 기준으로 해당 품목이 중소기업자간 경쟁제품인지 확인합니다.",
        f"- 추정가격이 {threshold} 미만인지 산정합니다. 맞다면 소기업·소상공인 제한경쟁입찰을 우선 검토합니다.",
        "- 직접생산확인증명서가 필요한 품목이면 입찰참가자격에 직접생산확인 범위와 유효기간 확인을 넣습니다.",
        "- 소기업·소상공인 입찰에서 유찰되거나 적격자가 없는 등 예외 사유가 생기면 중소기업자 간 제한경쟁으로 넓힐 수 있는지 근거를 남깁니다.",
        "- 부산 지역업체 참여까지 검토하려면 별도로 지역제한 가능 금액, 지역 내 경쟁 가능한 업체 수, 부당제한 여부를 확인해야 합니다.",
        "",
        f"정리하면, **{threshold} 미만이면 소기업·소상공인 제한을 먼저 검토하고, 예외 사유가 있을 때 중소기업자 간 제한으로 전환하는지 따져보는 순서**가 안전합니다.",
        "⚖️ 본 답변은 내부 법령 DB 기준의 참고 안내입니다. 공고 전에는 최신 조문 원문과 해당 품목 고시를 함께 확인하세요.",
    ])


def _is_sole_contract(q: str) -> bool:
    # 금액과 계약종류가 함께 들어온 실제 사안형 질문은 DB 근거를 붙인 LLM
    # 흐름으로 넘긴다. 여기서는 "한도/기준표" 설명형 질문만 빠르게 처리한다.
    if _extract_amount_won(q) is not None and _contract_kind(q) is not None:
        return False

    checklist_intent = any(
        term in q
        for term in ("확인사항", "확인할", "검토할때", "검토시", "체크", "유의", "주의", "절차", "흐름")
    )
    explicit_standard_intent = any(term in q for term in ("기준", "한도", "금액", "얼마"))
    if checklist_intent and not explicit_standard_intent:
        return False

    return (
        "수의계약" in q
        and any(term in q for term in ("기준", "한도", "금액", "얼마", "1인견적", "견적"))
    )


def _is_public_corp_direct_contract_difference(q: str) -> bool:
    return (
        ("공기업" in q or "준정부기관" in q)
        and "계약사무규칙" in q
        and "수의계약" in q
        and ("국가계약" in q or "뭐가달라" in q or "차이" in q)
    )


def _public_corp_direct_contract_difference_answer() -> str:
    return "\n".join([
        "공기업·준정부기관에서 **수의계약**을 볼 때는 「공기업·준정부기관 계약사무규칙」과 국가계약법령의 준용 구조를 나누어 확인해야 합니다.",
        "",
        "- **공기업·준정부기관 계약사무규칙**",
        "  - 기관 계약사무의 기본 규칙과 준용 범위를 먼저 봅니다.",
        "  - 규칙 자체에 별도 기준이 있으면 그 기준을 우선 확인하고, 별도 규정이 없으면 국가계약법령 준용 여부를 확인합니다.",
        "",
        "- **국가계약법과의 차이**",
        "  - 국가기관 기준을 그대로 복사하기보다, 해당 공기업·준정부기관의 내부 계약규정, 위임전결, 자체 지침을 함께 확인해야 합니다.",
        "  - 수의계약 사유, 견적 방식, 금액 기준은 기관 자체 기준에서 달라질 수 있으므로 공고·계약 전 원문 확인이 필요합니다.",
        "",
        "정리하면, 공기업·준정부기관은 국가계약법령을 참고하되 `국가기관과 완전히 동일`하다고 단정하지 말고, 계약사무규칙과 기관 내부 기준을 같이 보는 구조입니다.",
    ])


def _is_construction_repair_direct_limit_question(q: str) -> bool:
    return (
        ("보수공사" in q or "청사보수" in q)
        and "수의계약" in q
        and ("종합공사" in q or "전문공사" in q)
    )


def _construction_repair_direct_limit_answer() -> str:
    return "\n".join([
        "청사 **보수공사**는 먼저 공사 범위와 면허·업종을 나누어 **종합공사**인지 **전문공사**인지 판단해야 합니다.",
        "",
        "- 종합공사와 전문공사는 적용되는 수의계약 한도와 참가자격 검토가 달라질 수 있습니다.",
        "- 단순히 `보수`라는 명칭만으로 정하지 말고 설계서, 내역서, 공종, 주된 공사 내용, 필요한 면허를 함께 확인합니다.",
        "- 복수 공종이 섞이면 주된 공사와 부대공사 관계, 분리발주 필요성, 무면허 시공 리스크를 검토합니다.",
        "- 금액 한도는 최신 법령 DB와 source map resolved_value로 별도 확인해야 하며, 이 답변에서는 금액을 단정하지 않습니다.",
    ])


def _is_local_company_point(q: str) -> bool:
    if (
        any(term in q for term in ("공동도급", "지역제한"))
        and any(term in q for term in ("연결", "높이", "어떻게"))
    ):
        return False
    return (
        ("지역업체" in q or "지역기업" in q)
        and any(term in q for term in ("가점", "점수", "참여도", "신인도", "적격심사", "평가"))
    )


def _is_regional_mandatory_joint_contract(q: str) -> bool:
    if (
        any(term in q for term in ("지역제한", "적격심사"))
        and any(term in q for term in ("연결", "높이", "어떻게"))
    ):
        return False
    return (
        ("지역의무" in q or "의무공동" in q or ("공동도급" in q and "지역" in q))
        and any(term in q for term in ("기준", "비율", "몇", "가능", "공사", "발주", "공동도급"))
    )


def _is_mas_regional_review(q: str) -> bool:
    has_mas = any(term in q for term in ("mas", "종합쇼핑몰", "다수공급자", "제3자단가", "3자단가"))
    has_region = any(term in q for term in ("지역업체", "부산업체", "부산", "지역", "우대", "가점"))
    has_review = any(term in q for term in ("2단계", "경쟁", "우대", "가점", "고려", "활용", "가능", "살수", "구매"))
    return has_mas and has_region and has_review


def _is_excellent_procurement_or_third_party(q: str) -> bool:
    if "소프트웨어" in q:
        return False
    return (
        any(term in q for term in ("우수조달", "제3자단가", "3자단가", "제3자를위한단가"))
        and any(term in q for term in ("부산", "지역상품", "지역업체", "활용", "도움", "구매"))
    )


def _is_innovation_product_purchase_review(q: str) -> bool:
    return (
        any(term in q for term in ("혁신제품", "혁신시제품", "혁신장터"))
        and any(term in q for term in ("수의계약", "우선구매", "검토", "구매"))
        and not any(term in q for term in ("후보", "추천", "찾아", "검색"))
    )


def _innovation_product_purchase_review_answer() -> str:
    return "\n".join([
        "혁신제품·혁신시제품은 **지정 상태와 구매 경로를 먼저 확인한 뒤** 수의계약·우선구매 검토로 연결해야 합니다.",
        "",
        "- **혁신제품**",
        "  - 조달 관련 법령상 혁신제품 지정 여부, 지정 유효기간, 제품명·규격 일치 여부를 먼저 확인합니다.",
        "  - 지정이 유효한 경우 수의계약 특례 또는 혁신장터·조달 경로를 검토할 수 있습니다.",
        "",
        "- **혁신시제품**",
        "  - 명칭만으로 단정하지 말고, 현재 제도상 혁신제품 지정으로 전환되었는지, 시범구매 대상인지, 별도 특수조건이 붙는지 확인합니다.",
        "  - 제품·사업 단계에 따라 구매 절차와 계약조건이 달라질 수 있습니다.",
        "",
        "- **우선구매 연결**",
        "  - 혁신제품, 기술개발제품, 우수조달물품 등 지위가 중복될 수 있으므로 지정·인증 근거와 유효상태를 표로 정리합니다.",
        "  - 부산 지역업체 제품이면 지역상품 구매지원 취지와 연결할 수 있지만, 지역 소재만으로 수의계약 결론을 내리면 안 됩니다.",
        "",
        "확인할 근거: 「지방계약법 시행령」 수의계약 사유, 「조달사업법」 혁신제품 관련 규정, 혁신제품·기술개발제품 관련 고시·운영규정.",
        "금액·시행일·지정상태는 내부 법령 DB와 source map, 혁신장터 원자료로 별도 확인해야 합니다.",
    ])


def _is_audit_risk_review(q: str) -> bool:
    return (
        any(term in q for term in ("감사", "지적", "문제되지", "특혜", "부당"))
        and any(term in q for term in ("부산업체", "지역업체", "지역상품", "지역제한", "수의계약", "활용"))
    )


def _is_split_purchase_audit_review(q: str) -> bool:
    return (
        any(term in q for term in ("쪼개기", "분할발주", "나눠", "여러번"))
        and any(term in q for term in ("수의계약", "감사", "대응", "자료"))
    )


def _split_purchase_audit_review_answer(q: str) -> str:
    item = "컴퓨터" if "컴퓨터" in q else "같은 물품"
    return "\n".join([
        f"{item}를 같은 부서에서 여러 번 나눠 구매하면 **쪼개기 수의계약** 또는 분할발주 의심을 받을 수 있습니다.",
        "",
        "- **먼저 볼 점**",
        "  - 같은 목적, 같은 예산, 같은 시기, 같은 수요부서의 구매를 인위적으로 나누었는지 확인합니다.",
        "  - 추정가격 산정 시 동일·유사 물품 수요를 합산했는지, 부서별·기간별 분리 사유가 객관적인지 확인합니다.",
        "",
        "- **감사 대응 자료**",
        "  - 수요조사 자료, 예산 편성·배정 내역, 구매 필요 시점, 고장·증설 등 긴급·추가 수요 발생 근거를 남깁니다.",
        "  - 시장조사, 견적 비교, 세부품명·규격 결정 사유, 반복 구매 사유서를 보관합니다.",
        "  - 통합발주 가능성을 검토했고 왜 나누었는지 결재문서에 남기는 편이 안전합니다.",
        "",
        "정리하면, 나누어 샀다는 사실만으로 항상 위법이라고 단정할 수는 없지만, 금액 기준이나 경쟁절차를 피하려는 구조로 보이면 감사 리스크가 큽니다.",
    ])


def _regional_restriction_answer(q: str) -> str:
    wants_national = "국가" in q
    wants_public_corp = "공기업" in q or "준정부" in q or "공공기관" in q
    wants_local = "지방" in q or "지방자치단체" in q or "지자체" in q
    asks_multiple = sum([wants_national, wants_public_corp, wants_local]) >= 2
    if not any([wants_national, wants_public_corp, wants_local]) or asks_multiple:
        wants_national = wants_public_corp = wants_local = True

    national_amount = _money_limit("P_NATIONAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD", " 미만")
    public_corp_amount = _money_limit("P_PUBLIC_CORP_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD", " 미만")
    local_amount = _money_limit("P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD", " 미만")

    lines = ["종합공사 지역제한 기준은 **기관유형별 기준값을 나누어** 봐야 합니다.", ""]
    if wants_national:
        lines += _regional_amount_line(
            "국가기관",
            "P_NATIONAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD",
            "「국가계약법 시행규칙」 제24조제2항제1호가목 + 국가계약법 제4조제1항 고시금액",
        )
    if wants_public_corp:
        lines += _regional_amount_line(
            "공기업ㆍ준정부기관",
            "P_PUBLIC_CORP_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD",
            "「공기업ㆍ준정부기관 계약사무규칙」 제6조제4항제1호가목",
        )
    if wants_local:
        lines += _regional_amount_line(
            "지방자치단체",
            "P_LOCAL_LIMITED_BID_GENERAL_CONSTRUCTION_THRESHOLD",
            "「지방계약법 시행규칙」 제24조제1호가목",
        )

    if wants_national and wants_public_corp and wants_local:
        summary = f"국가기관만 `고시금액`을 따라 현재 **{national_amount}**이고, 공기업ㆍ준정부기관은 **{public_corp_amount}**, 지방자치단체는 **{local_amount}**입니다."
    elif wants_national:
        summary = f"국가기관의 종합공사는 국가계약법상 `고시금액`을 따라 현재 **{national_amount}** 기준으로 봅니다."
    elif wants_public_corp:
        summary = f"공기업ㆍ준정부기관의 종합공사 지역제한 기준은 **{public_corp_amount}**입니다."
    else:
        summary = f"지방자치단체의 종합공사 지역제한 기준은 **{local_amount}**입니다."

    lines += [
        "",
        summary,
        "",
        "실무 적용 시에는 추정가격 기준인지, 전문공사인지, 그 밖의 공사 관련 법령에 따른 공사인지 확인해야 합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 최신 법령과 고시금액 기준을 바탕으로 한 참고 안내입니다.",
    ]
    return "\n".join(lines)


def _extract_amount_won(q: str) -> int | None:
    match = re.search(r"(\d+(?:\.\d+)?)억", q)
    if match:
        return int(float(match.group(1)) * 100_000_000)

    match = re.search(r"(\d+(?:\.\d+)?)천만", q)
    if match:
        return int(float(match.group(1)) * 10_000_000)

    match = re.search(r"(\d+(?:\.\d+)?)백만", q)
    if match:
        return int(float(match.group(1)) * 1_000_000)

    match = re.search(r"(\d+(?:\.\d+)?)만원", q)
    if match:
        return int(float(match.group(1)) * 10_000)

    return None


def _contract_kind(q: str) -> str | None:
    if any(term in q for term in ("종합공사", "전문공사", "건설공사", "공사")):
        return "construction"
    if any(term in q for term in ("용역", "학술", "기술용역")):
        return "service"
    if any(term in q for term in ("물품", "구매", "제조", "납품", "제품")):
        return "goods"
    return None


def _sole_contract_answer(q: str) -> str:
    general_construction = _money_limit("P_DIRECT_GENERAL_CONSTRUCTION_THRESHOLD")
    specialty_construction = _money_limit("P_DIRECT_SPECIALTY_CONSTRUCTION_THRESHOLD")
    other_construction = _money_limit("P_DIRECT_OTHER_CONSTRUCTION_THRESHOLD")
    general_goods_service = _money_limit("P_LOCAL_DIRECT_GENERAL_GOODS_SERVICE_THRESHOLD")
    policy_company = _money_limit("P_LOCAL_DIRECT_POLICY_COMPANY_THRESHOLD")
    one_quote_general = _money_limit("P_LOCAL_DIRECT_ONE_QUOTE_GENERAL_THRESHOLD")
    one_quote_policy = _money_limit("P_LOCAL_DIRECT_ONE_QUOTE_POLICY_COMPANY_THRESHOLD")

    return "\n".join([
        "수의계약은 **계약 종류와 견적 방식**을 나누어 봐야 합니다.",
        "",
        "- **공사 수의계약 금액 기준**",
        f"  - 종합공사: **추정가격 {general_construction}**",
        f"  - 전문공사: **추정가격 {specialty_construction}**",
        f"  - 그 밖의 공사 관련 법령에 따른 공사: **추정가격 {other_construction}**",
        "  근거: 「지방계약법 시행령」 제25조제1항제5호가목, 「국가계약법 시행령」 제26조제1항제5호가목",
        "",
        "- **물품ㆍ용역 일반 기준**",
        f"  - 일반 물품ㆍ용역: **추정가격 {general_goods_service}**",
        f"  - 소기업ㆍ소상공인, 여성기업, 장애인기업, 사회적기업 등 정책기업 요건에 해당하는 일부 물품ㆍ용역: **추정가격 {policy_company}** 범위의 수의계약 근거가 있습니다.",
        "  근거: 「지방계약법 시행령」 제25조제1항제5호, 「국가계약법 시행령」 제26조제1항제5호",
        "",
        "- **1인 견적 가능 기준은 별도입니다**",
        f"  - 기본: **{one_quote_general}**",
        f"  - 청년창업기업ㆍ여성기업ㆍ장애인기업 등 일부 정책기업: **{one_quote_policy}**까지 1인 견적 가능 범위가 열립니다.",
        "  근거: 「지방계약법 시행령」 제30조, 「국가계약법 시행령」 제30조",
        "",
        "따라서 `수의계약 가능`과 `1인 견적으로 바로 가능`은 같은 말이 아닙니다. 실제 발주에서는 품목, 기관유형, 추정가격, 정책기업 자격, 직접생산 여부, 분할발주 금지 여부를 같이 확인해야 합니다.",
        "",
        "지역상품 구매 지원 관점에서는 먼저 부산 업체가 정책기업ㆍ직접생산ㆍ조달등록 요건을 갖췄는지 확인한 뒤, 수의계약이 불안하면 2인 이상 견적 또는 지역제한경쟁입찰로 연결하는 방식이 안전합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령 기준을 바탕으로 한 참고 안내입니다.",
    ])


def _local_company_point_answer(q: str) -> str:
    wants_national = "국가" in q or "중앙" in q or "정부기관" in q
    wants_public_corp = "공기업" in q or "준정부" in q or "공공기관" in q
    wants_local = "지방" in q or "지방자치단체" in q or "지자체" in q
    asks_multiple = sum([wants_national, wants_public_corp, wants_local]) >= 2
    if not any([wants_national, wants_public_corp, wants_local]) or asks_multiple:
        wants_national = wants_public_corp = wants_local = True

    full_rate = _num("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_FULL_RATE")
    full_score = _num("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_FULL_SCORE")
    partial_rate = _num("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_PARTIAL_RATE")
    partial_score = _num("P_LOCAL_SERVICE_REGIONAL_PARTICIPATION_PARTIAL_SCORE")
    national_min_share = _num("P_NATIONAL_JOINT_CONTRACT_MIN_SHARE")

    lines = [
        "맞습니다. **지역업체 참여도ㆍ가점은 조문만 보면 안 되고, 낙찰자 결정기준의 별표ㆍ세부심사기준ㆍ공고문 평가표까지 내려가야 합니다.**",
        "본문 조문은 `가점을 둘 수 있는 근거`를 보여주는 뼈대이고, 실제 배점ㆍ참여비율ㆍ계산방식은 예규의 장ㆍ별표ㆍ붙임 또는 해당 입찰공고의 평가표에 들어 있는 경우가 많습니다.",
        "",
        "### 1. 지역업체 우대 배점 확인 5단계 알고리즘",
        "| 단계 | 확인할 것 | 실제로 열어볼 문서 | 실무 포인트 |",
        "|---|---|---|---|",
        "| 1단계 | 발주처 정체성 | 기관 설립근거, 계약규정, 공고문 첫 부분 | 국가기관ㆍ국가공기업인지, 지방자치단체ㆍ지방공기업인지 먼저 나눕니다. 여기서 적용 법체계가 갈립니다. |",
        "| 2단계 | 계약대상과 낙찰방식 | 입찰공고, 제안요청서, 적격심사 기준 적용 문구 | 공사ㆍ용역ㆍ물품인지, 적격심사ㆍ종합평가ㆍ협상계약ㆍMAS 2단계경쟁인지 확정합니다. |",
        "| 3단계 | 핵심 행정규칙 검색 | 법령정보센터(law.go.kr)의 행정규칙 | 지방계약은 「지방자치단체 입찰시 낙찰자 결정기준」, 국가계약은 「(계약예규) 적격심사기준」ㆍ「(계약예규) 공동계약운용요령」부터 봅니다. |",
        "| 4단계 | 별표ㆍ세부심사표 추적 | 해당 예규의 장, 별표, 붙임, 세부심사방법 | 실제 `몇 점`인지는 여기 있습니다. 조문 검색에서 멈추지 말고 사업 유형ㆍ금액구간에 맞는 별표까지 내려갑니다. |",
        "| 5단계 | 공고문 최종 확인 | 나라장터 공고문, 과업지시서, 제안요청서, 평가표 | 상위 법령ㆍ예규 범위 안에서 해당 공고가 어떤 기준을 적용한다고 명시했는지가 최종 실무 기준입니다. 자체 적격심사 세부기준이 있으면 반드시 함께 봅니다. |",
        "",
        "### 2. 사업 유형별 별표 추적 포인트",
        "| 사업 구분 | 확인할 구체 경로 | 봐야 할 항목 |",
        "|---|---|---|",
        "| 시설공사 | 시설공사 적격심사ㆍ종합평가 관련 장과 별표 | 지역업체 참여비율, 지역의무공동도급 여부, 공동수급체 지분율, 공사 금액구간별 배점 |",
        "| 기술ㆍ학술용역 | 용역 적격심사 세부기준 별표 | 지역업체 합산 참여비율, 참여도 점수, 공동수급체 구성 방식 |",
        "| 일반용역ㆍ협상계약 | 낙찰자 결정기준, 협상계약 평가기준, 제안요청서 평가표 | 지역 이해도, 현장 대응성, 지역업체 참여계획, 지역 자원 활용계획이 정당한 평가항목인지 |",
        "| 물품구매 | 물품 적격심사 세부기준, MAS 2단계경쟁 기준, 공고 특수조건 | 물품은 지역가점보다 제조ㆍ직접생산, 정책기업, 납품지역, A/S, 쇼핑몰 등록 여부가 더 중요할 수 있습니다. |",
        "",
    ]

    if wants_local:
        lines += [
            "### 3. 지방계약 대상이면 이렇게 봅니다",
            "- **먼저 열 문서**: 「지방자치단체 입찰시 낙찰자 결정기준」.",
            "- **다음 확인**: 공사ㆍ용역ㆍ물품 중 해당 장을 열고, 그 장의 별표ㆍ세부심사기준에서 `지역업체 참여도`, `지역업체 합산 참여비율`, `지역의무공동도급`, `지역업체 참여계획` 항목을 찾습니다.",
            f"- **대표 예시**: 기술ㆍ학술용역 적격심사에서는 지역업체 합산 참여비율 **{full_rate} 이상: {full_score}**, **{partial_rate} 이상 {full_rate} 미만: {partial_score}** 같은 참여도 점수 구조가 쓰일 수 있습니다.",
            "- **주의**: 이 숫자는 질문 유형을 설명하기 위한 대표 기준입니다. 실제 적용은 해당 공고가 적용한다고 명시한 최신 예규 번호, 사업 유형, 금액구간, 별표를 기준으로 확정해야 합니다.",
            "",
        ]

    if wants_national:
        lines += [
            "### 4. 국가계약 대상이면 이렇게 봅니다",
            "- **먼저 열 문서**: 「국가계약법 시행령」에서 공동계약ㆍ제한경쟁의 근거를 확인한 뒤, 실제 배점은 「(계약예규) 적격심사기준」, 「(계약예규) 공동계약운용요령」, 분야별 세부기준에서 찾습니다.",
            "- **핵심 구분**: 국가계약은 `모든 계약에 지역업체 가점 몇 점`이라는 단일 표가 있는 구조가 아닙니다. 가점인지, 지역업체 의무참여인지, 공동수급 허용인지부터 나눠야 합니다.",
            f"- **대표 예시**: 「국가계약법 시행령」 제72조와 「공동계약운용요령」 제9조는 일정 공동계약에서 지역업체 최소 지분율을 **{national_min_share} 이상**으로 두는 구조를 둡니다.",
            "- **주의**: 국가기관이 지방계약의 별표 점수를 그대로 가져와 쓰면 부당한 평가기준이 될 수 있습니다.",
            "",
        ]

    if wants_public_corp:
        lines += [
            "### 5. 공기업ㆍ준정부기관이면 이렇게 봅니다",
            "- **먼저 열 문서**: 「공기업ㆍ준정부기관 계약사무규칙」과 해당 기관의 계약규정ㆍ입찰공고.",
            "- **다음 확인**: 규칙에 없는 사항은 국가계약법령을 준용하는 구조인지, 기관별 계약기준ㆍ자체 적격심사 세부기준이나 제안서 평가기준을 따로 두는지 봅니다.",
            "- **주의**: 계약사무규칙 자체에 지역업체 가점 단일 점수표가 바로 들어 있는 구조가 아닙니다. 지역제한은 같은 규칙 제6조의 입찰참가자격 제한 장치이고, 가점ㆍ참여도와는 구분해야 합니다.",
            "",
        ]

    lines += [
        "### 6. 공고문에서 마지막으로 확인할 문구",
        "- `본 입찰은 ○○ 예규 제○호 「○○ 낙찰자 결정기준」을 적용한다`",
        "- `지역업체 참여도는 별표 ○의 산식에 따라 평가한다`",
        "- `공동수급체 구성 시 지역업체 참여비율을 평가한다`",
        "- `기관 자체 적격심사 세부기준 또는 제안서 평가기준을 적용한다`",
        "",
        "정리하면, **조문에서 근거를 확인하고, 예규ㆍ낙찰자 결정기준의 별표에서 점수를 찾은 뒤, 나라장터 공고문과 평가표에서 최종 적용 기준을 확정**해야 합니다. `부산업체라서 무조건 가점`이 아니라, 해당 계약의 기관유형ㆍ사업유형ㆍ낙찰방식ㆍ별표 항목 안에서 허용되는지를 확인하는 순서입니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령ㆍ행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ]
    return "\n".join(lines)


def _mas_regional_review_answer(q: str) -> str:
    item = _item_hint(q)
    item_prefix = f"**{item}** 구매처럼 품목이 정해진 경우에는, " if item else ""
    item_example = item or "LED, CCTV, 사무가구"
    return "\n".join([
        f"{item_prefix}종합쇼핑몰/MAS 2단계 경쟁에서는 **부산업체라는 이유만으로 지역제한을 걸거나 별도 가점을 주는 방식은 신중해야 합니다.**",
        "다만 부산 지역상품 구매 지원 관점에서 활용할 수 있는 실무 경로는 있습니다.",
        "",
        "- **1. 부산 MAS 등록업체를 후보군으로 먼저 찾기**",
        "  - 구매 품목을 확정한 뒤 종합쇼핑몰에서 부산 소재 공급업체, 납품 가능 지역, 계약상태, 규격 일치 여부를 확인합니다.",
        "  - 이는 특정 업체 특혜가 아니라 제안요청 전 후보 탐색과 시장조사 단계로 정리하는 것이 안전합니다.",
        "",
        "- **2. 2단계 경쟁에서는 평가항목 안에서만 지역 장점을 반영**",
        "  - 지역업체 자체를 독립 가점으로 두기보다 납기, 사후관리, 현장지원, 유지보수 대응 같은 정당한 평가요소와 연결해야 합니다.",
        "  - 부산 업체가 빠른 A/S나 납품 대응을 제안서에 제시하면, 그 내용이 공고된 평가항목과 맞는 범위에서 검토될 수 있습니다.",
        "",
        "- **3. 지역제한경쟁입찰과 MAS 2단계 경쟁은 구분**",
        "  - 지방계약법령상 지역제한은 일반 경쟁입찰의 참가자격 제한 장치입니다.",
        "  - MAS 2단계 경쟁에서는 조달청 다수공급자계약 체계와 종합쇼핑몰 운영규정, 물품 다수공급자계약 업무처리규정을 우선 확인해야 합니다.",
        "",
        "- **4. 품목이 정해졌다면 업체 후보까지 붙여야 실무 답변이 됩니다**",
        f"  - 예: {item_example}처럼 세부품명이 있으면 부산 MAS 등록업체, 조달등록 여부, 인증제품 여부를 함께 조회해 구매 경로를 정리합니다.",
        "  - 품목이 없는 제도 질문이면 여기서는 원칙과 확인 순서까지만 안내하는 것이 적절합니다.",
        "",
        "정리하면, **MAS에서 부산업체를 직접 우대한다고 단정하기보다는, 부산 MAS 등록업체를 후보로 발굴하고 납기ㆍA/Sㆍ현장지원 등 정당한 평가요소로 연결하는 방식**이 안전합니다.",
        "근거: 「조달사업에 관한 법률」, 「국가종합전자조달시스템 종합쇼핑몰 운영규정」, 「물품 다수공급자계약 업무처리규정」",
        "⚖️ 본 답변은 내부 DB에 적재된 조달 관련 행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ])


def _excellent_procurement_or_third_party_answer() -> str:
    return "\n".join([
        "우수조달물품이나 **제3자단가계약** 제품은 부산 지역상품 구매지원에 도움이 될 수 있습니다. 다만 `부산업체라서 바로 수의계약 가능`으로 보지 말고, 제품 지정ㆍ계약상태ㆍ납품요구 가능 여부를 순서대로 확인해야 합니다.",
        "",
        "- **우수조달물품**",
        "  - 조달청 우수조달물품 지정 제품인지, 지정 상태가 유효한지 확인합니다.",
        "  - 구매하려는 규격과 우수조달 지정 제품명이 같은지 확인해야 합니다.",
        "  - 부산업체 제품이면 지역상품 구매 취지와 연결할 수 있지만, 우수조달 지정 자체와 부산 소재 여부는 별도 요건입니다.",
        "",
        "- **제3자단가계약/종합쇼핑몰 경로**",
        "  - 나라장터 종합쇼핑몰 등록 여부, 계약기간, 납품 가능 지역, 납품요구 한도와 2단계 경쟁 대상 여부를 확인합니다.",
        "  - 부산 공급업체가 있으면 시장조사와 후보 검토 자료로 활용하되, 특정 업체를 미리 정한 것처럼 공고ㆍ평가를 설계하면 안 됩니다.",
        "",
        "- **실무 처리 방향**",
        "  - 품목명이 정해지면 부산업체 후보, 쇼핑몰/MAS 등록, 우수조달ㆍ혁신제품ㆍ성능인증 여부를 함께 조회합니다.",
        "  - 답변에는 `계약 가능` 단정 대신 `등록상태, 지정ㆍ인증 상태, 규격 일치, 기관유형별 절차 확인 후 검토 가능`으로 표시하는 것이 안전합니다.",
        "",
        "⚖️ 본 답변은 내부 DB와 구매지원 카탈로그 기준의 실무 안내입니다.",
    ])


def _audit_risk_review_answer() -> str:
    return "\n".join([
        "부산업체를 활용할 때 감사에서 문제되지 않게 하려면 핵심은 **지역상품 구매지원 목적**과 **계약법상 경쟁성ㆍ공정성**을 함께 남기는 것입니다.",
        "",
        "- **1. 특정 업체를 먼저 정하지 않기**",
        "  - 시장조사는 가능하지만, 공고조건ㆍ규격ㆍ평가항목이 특정 부산업체만 맞출 수 있게 작성되면 특혜 시비가 생길 수 있습니다.",
        "  - 과업지시서에는 `부산업체 수행` 같은 직접 조건보다 과업 수행에 필요한 현장 대응, 납기, 유지관리, 의사소통, 품질관리 기준을 객관적으로 적어야 합니다.",
        "  - 업체 후보표는 `검토 후보`로 관리하고, 계약 가능 여부는 별도 확인으로 남깁니다.",
        "",
        "- **2. 지역제한ㆍ지역의무공동도급ㆍ지역업체 가점은 제도별 요건 확인**",
        "  - 지역제한은 계약목적물과 금액 기준, 본점 소재지, 경쟁 가능한 업체 수를 확인해야 합니다.",
        "  - 지역의무공동도급은 주로 공사에서 검토하며, 지역업체 수와 공동수급체 구성 가능성을 확인해야 합니다.",
        "  - 가점ㆍ참여도는 기관유형과 낙찰자 결정기준, 입찰공고 평가항목에 근거가 있어야 합니다.",
        "",
        "- **3. 수의계약은 금액ㆍ사유ㆍ견적방식을 문서화**",
        "  - 소액수의, 정책기업, 기술개발제품, 우수조달물품 등은 각각 근거와 한도가 다릅니다.",
        "  - `부산업체라서 수의계약`이 아니라, 해당 법령상 사유와 금액 기준을 먼저 확인해야 합니다.",
        "",
        "- **4. 남겨야 할 확인 자료**",
        "  - 적용 법령 조문, 기준금액 산정 근거, 세부품명/규격 결정 이유, 후보업체 비교표, 인증ㆍ쇼핑몰 등록 상태, 견적 또는 평가 기록을 남깁니다.",
        "  - 내부 검토서에는 `지역상품 구매지원 목적`, `경쟁성 확보 방식`, `특정업체 배제ㆍ특혜 방지 조치`를 함께 적는 것이 좋습니다.",
        "",
        "정리하면, 부산업체 활용 자체가 문제라기보다 **근거 없는 제한, 특정업체 맞춤 규격, 수의계약 사유 누락, 후보 검증 미기록**이 감사 리스크입니다.",
    ])


def _regional_mandatory_joint_contract_answer(q: str = "") -> str:
    min_share = _num("P_LOCAL_JOINT_CONTRACT_MIN_SHARE")
    max_share = _num("P_LOCAL_JOINT_CONTRACT_MAX_SHARE")
    min_company_count = _num("P_LOCAL_JOINT_CONTRACT_MIN_QUALIFIED_COMPANY_COUNT")
    public_corp_note = []
    if "공기업" in q or "준정부" in q or "공공기관" in q:
        public_corp_note = [
            "",
            "- **공기업ㆍ준정부기관에서의 추가 확인**",
            "  - 공기업ㆍ준정부기관은 「공기업ㆍ준정부기관 계약사무규칙」과 기관 자체 계약기준, 입찰공고 조건을 함께 확인해야 합니다.",
            "  - 지역업체 공동도급을 검토할 때도 국가계약법령 준용 여부, 기관 내부 기준, 공사 성격, 공동수급체 구성 가능성을 먼저 확인해야 합니다.",
            "  - 지방자치단체 기준의 지역의무공동도급 비율을 공기업 계약에 그대로 적용한다고 단정하면 안 됩니다.",
            "  근거: 「공기업ㆍ준정부기관 계약사무규칙」 및 공동계약 관련 내부 DB 기준",
        ]

    return "\n".join([
        "지역의무공동도급은 지역업체 참여를 강제해 지역 시공 참여를 확보하는 장치입니다. 전기공사 같은 공사에서 검토할 수 있고, 핵심은 **공사에 한해** 적용한다는 점입니다.",
        "지역제한은 참가자격을 지역으로 제한하는 장치이고, 지역의무공동도급은 공동수급체 안에 지역업체 참여비율을 두는 장치라서 서로 구분해 검토해야 합니다.",
        "",
        "- **적용 대상**",
        "  - 지방계약에서 공동계약을 체결하는 경우, 지역경제 활성화를 위해 지역업체 참여비율을 정할 수 있습니다.",
        "  - 「지방자치단체 입찰 및 계약집행기준」은 **공사의 경우에만 지역의무 공동도급으로 발주할 수 있다**고 정합니다.",
        "  근거: 「지방계약법 시행령」 제88조, 「지방자치단체 입찰 및 계약집행기준」 공동계약 운영요령",
        "",
        "- **지역업체 최소 시공참여비율**",
        f"  - 원칙: 해당 시ㆍ도 소재 지역업체의 최소 시공참여비율 **{min_share}**를 입찰공고에 명시",
        f"  - 지역경제 활성화 필요성이 있으면 **{max_share} 이하의 범위**에서 정할 수 있습니다.",
        "",
        "- **발주하면 안 되거나 조정이 필요한 경우**",
        f"  - 최소 참여비율 이상을 충족할 시공능력평가액을 갖춘 지역업체가 {min_company_count} 미만인 경우",
        f"  - {min_share} 이상 지역업체로 제한할 때 필요한 면허ㆍ등록 자격을 갖춘 지역업체가 {min_company_count} 미만인 경우",
        "  - 품질 저하 우려나 공동수급체 구성이 곤란한 경우",
        "  - 지역업체 수를 과도하게 제한하거나 특정 지역업체 하도급ㆍ자재납품을 의무화하는 방식은 부당 제한이 될 수 있습니다.",
        *public_corp_note,
        "",
        "지역상품 구매 지원 관점에서는 대형 공사에서 부산 지역업체 참여를 제도적으로 확보하는 데 유용하지만, 입찰공고 단계에서 비율ㆍ면허ㆍ시공능력ㆍ업체 수를 먼저 확인해야 합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령ㆍ행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ])
