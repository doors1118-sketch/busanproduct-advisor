"""
Deterministic legal answer gate for high-frequency procurement standards.

These answers cover narrow, repeatedly asked 기준/정의/한도 questions where
free-form LLM generation tends to add noise or mix unrelated thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
import re

from policies.numeric_basis_policy import get_numeric_display


@dataclass(frozen=True)
class DeterministicLegalAnswer:
    answer: str
    reason: str
    schema_version: str


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


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

    if _is_mas_regional_review(q):
        return DeterministicLegalAnswer(
            answer=_mas_regional_review_answer(q),
            reason="mas_regional_review_fast_answer",
            schema_version="mas_regional_review_v1",
        )

    if _is_regional_mandatory_joint_contract(q):
        return DeterministicLegalAnswer(
            answer=_regional_mandatory_joint_contract_answer(),
            reason="regional_mandatory_joint_contract_fast_answer",
            schema_version="regional_mandatory_joint_contract_v1",
        )

    return None


def _is_regional_restriction(q: str) -> bool:
    return (
        ("지역제한" in q or "지역제한경쟁" in q)
        and ("종합공사" in q or "건설공사" in q)
        and any(term in q for term in ("기준", "금액", "얼마", "몇억", "100억", "150억", "88억"))
    )


def _is_sole_contract(q: str) -> bool:
    # 금액과 계약종류가 함께 들어온 실제 사안형 질문은 DB 근거를 붙인 LLM
    # 흐름으로 넘긴다. 여기서는 "한도/기준표" 설명형 질문만 빠르게 처리한다.
    if _extract_amount_won(q) is not None and _contract_kind(q) is not None:
        return False

    return (
        "수의계약" in q
        and any(term in q for term in ("기준", "한도", "금액", "얼마", "1인견적", "견적"))
    )


def _is_local_company_point(q: str) -> bool:
    return (
        ("지역업체" in q or "지역기업" in q)
        and any(term in q for term in ("가점", "점수", "참여도", "신인도", "적격심사", "평가"))
    )


def _is_regional_mandatory_joint_contract(q: str) -> bool:
    return (
        ("지역의무" in q or "의무공동" in q or ("공동도급" in q and "지역" in q))
        and any(term in q for term in ("기준", "비율", "몇", "가능", "공사", "발주", "공동도급"))
    )


def _is_mas_regional_review(q: str) -> bool:
    has_mas = any(term in q for term in ("mas", "종합쇼핑몰", "다수공급자", "제3자단가", "3자단가"))
    has_region = any(term in q for term in ("지역업체", "부산업체", "부산", "지역", "우대", "가점"))
    has_review = any(term in q for term in ("2단계", "경쟁", "우대", "가점", "고려", "활용", "가능", "살수", "구매"))
    return has_mas and has_region and has_review


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
        "맞습니다. **지역업체 가점ㆍ우대는 기관유형별로 같은 제도가 아닙니다.**",
        "소속기관을 먼저 확정한 뒤, 해당 기관의 낙찰자 결정기준과 입찰공고 기준으로 봐야 합니다.",
        "",
    ]

    if wants_local:
        lines += [
            "- **지방자치단체**",
            "  - 기술ㆍ학술용역 적격심사에는 `지역업체 참여도` 점수항목이 있습니다.",
            f"  - 지역업체 합산 참여비율 **{full_rate} 이상: {full_score}**, **{partial_rate} 이상 {full_rate} 미만: {partial_score}**이 대표 기준입니다.",
            "  - 시설공사ㆍPQ 등에서는 지역업체 합산시공비율, 전문화 지역업체 참여도, 소규모 공사 접근성 가산 등으로 별도 평가될 수 있습니다.",
            "  근거: 「지방자치단체 입찰시 낙찰자 결정기준」",
            "",
        ]

    if wants_national:
        lines += [
            "- **국가기관**",
            "  - 국가계약법령 자체에 `모든 계약에 지역업체 가점 몇 점`처럼 일괄 적용되는 단일 점수표가 있는 구조는 아닙니다.",
            "  - 지역업체 우대는 주로 공동계약ㆍ지역업체 의무참여 또는 세부심사기준ㆍ입찰공고의 평가항목으로 나타납니다.",
            f"  - 예를 들어 「국가계약법 시행령」 제72조와 「공동계약운용요령」 제9조는 일정 공동계약에서 지역업체 최소 지분율을 **{national_min_share} 이상**으로 두는 구조를 둡니다.",
            "  - 따라서 국가기관 질문에서는 `가점`인지 `지역업체 의무참여`인지 먼저 구분해야 합니다.",
            "  근거: 「국가계약법 시행령」 제72조, 「(계약예규) 공동계약운용요령」 제9조",
            "",
        ]

    if wants_public_corp:
        lines += [
            "- **공기업ㆍ준정부기관**",
            "  - 「공기업ㆍ준정부기관 계약사무규칙」은 별도 규정이 없는 사항에 대해 국가계약법령을 준용하는 구조입니다.",
            "  - 이 규칙 자체에 지역업체 가점 단일 점수표가 곧바로 박혀 있다기보다, 기관별 계약기준ㆍ입찰공고ㆍ세부평가기준에서 지역업체 우대 여부를 확인해야 합니다.",
            "  - 지역제한은 같은 규칙 제6조에서 별도로 다루지만, 이것은 `가점`과는 다른 입찰참가자격 제한 장치입니다.",
            "  근거: 「공기업ㆍ준정부기관 계약사무규칙」 제2조제5항, 제6조",
            "",
        ]

    lines += [
        "지역상품 구매 지원 관점에서는 `부산업체라서 무조건 가점`으로 답하면 위험합니다. 먼저 소속기관을 확정하고, 그 다음 계약종류가 물품ㆍ용역ㆍ공사인지, 평가방식이 적격심사ㆍ종합평가ㆍ협상계약인지, 입찰공고에 지역업체 참여도 항목이 있는지를 순서대로 확인해야 합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령ㆍ행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ]
    return "\n".join(lines)


def _mas_regional_review_answer(q: str) -> str:
    return "\n".join([
        "종합쇼핑몰/MAS 2단계 경쟁에서는 **부산업체라는 이유만으로 지역제한을 걸거나 별도 가점을 주는 방식은 신중해야 합니다.**",
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
        "  - 예: LED, CCTV, 사무가구처럼 세부품명이 있으면 부산 MAS 등록업체, 조달등록 여부, 인증제품 여부를 함께 조회해 구매 경로를 정리합니다.",
        "  - 품목이 없는 제도 질문이면 여기서는 원칙과 확인 순서까지만 안내하는 것이 적절합니다.",
        "",
        "정리하면, **MAS에서 부산업체를 직접 우대한다고 단정하기보다는, 부산 MAS 등록업체를 후보로 발굴하고 납기ㆍA/Sㆍ현장지원 등 정당한 평가요소로 연결하는 방식**이 안전합니다.",
        "근거: 「조달사업에 관한 법률」, 「국가종합전자조달시스템 종합쇼핑몰 운영규정」, 「물품 다수공급자계약 업무처리규정」",
        "⚖️ 본 답변은 내부 DB에 적재된 조달 관련 행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ])


def _regional_mandatory_joint_contract_answer() -> str:
    min_share = _num("P_LOCAL_JOINT_CONTRACT_MIN_SHARE")
    max_share = _num("P_LOCAL_JOINT_CONTRACT_MAX_SHARE")
    min_company_count = _num("P_LOCAL_JOINT_CONTRACT_MIN_QUALIFIED_COMPANY_COUNT")

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
        "",
        "지역상품 구매 지원 관점에서는 대형 공사에서 부산 지역업체 참여를 제도적으로 확보하는 데 유용하지만, 입찰공고 단계에서 비율ㆍ면허ㆍ시공능력ㆍ업체 수를 먼저 확인해야 합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령ㆍ행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ])
