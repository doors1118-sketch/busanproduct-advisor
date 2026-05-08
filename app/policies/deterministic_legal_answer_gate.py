"""
Deterministic legal answer gate for high-frequency procurement standards.

These answers cover narrow, repeatedly asked 기준/정의/한도 questions where
free-form LLM generation tends to add noise or mix unrelated thresholds.
"""
from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class DeterministicLegalAnswer:
    answer: str
    reason: str
    schema_version: str


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


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


def _regional_restriction_answer(q: str) -> str:
    wants_national = "국가" in q
    wants_public_corp = "공기업" in q or "준정부" in q or "공공기관" in q
    wants_local = "지방" in q or "지방자치단체" in q or "지자체" in q
    asks_multiple = sum([wants_national, wants_public_corp, wants_local]) >= 2
    if not any([wants_national, wants_public_corp, wants_local]) or asks_multiple:
        wants_national = wants_public_corp = wants_local = True

    lines = ["종합공사 기준으로 보면 **100억원이 아니라 아래 금액이 맞습니다.**", ""]
    if wants_national:
        lines += [
            "- **국가기관**: **88억원 미만**",
            "  근거: 「국가계약법 시행규칙」 제24조제2항제1호가목 + 국가계약법 제4조제1항 고시금액",
        ]
    if wants_public_corp:
        lines += [
            "- **공기업ㆍ준정부기관**: **150억원 미만**",
            "  근거: 「공기업ㆍ준정부기관 계약사무규칙」 제6조제4항제1호가목",
        ]
    if wants_local:
        lines += [
            "- **지방자치단체**: **150억원 미만**",
            "  근거: 「지방계약법 시행규칙」 제24조제1호가목",
        ]

    if wants_national and wants_public_corp and wants_local:
        summary = "국가기관만 `고시금액`을 따라 현재 **88억원 미만**이고, 공기업ㆍ준정부기관과 지방자치단체는 **150억원 미만**입니다."
    elif wants_national:
        summary = "국가기관의 종합공사는 국가계약법상 `고시금액`을 따라 현재 **88억원 미만** 기준으로 봅니다."
    elif wants_public_corp:
        summary = "공기업ㆍ준정부기관의 종합공사 지역제한 기준은 **150억원 미만**입니다."
    else:
        summary = "지방자치단체의 종합공사 지역제한 기준은 **150억원 미만**입니다."

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
    return "\n".join([
        "수의계약은 **계약 종류와 견적 방식**을 나누어 봐야 합니다.",
        "",
        "- **공사 수의계약 금액 기준**",
        "  - 종합공사: **추정가격 4억원 이하**",
        "  - 전문공사: **추정가격 2억원 이하**",
        "  - 그 밖의 공사 관련 법령에 따른 공사: **추정가격 1억6천만원 이하**",
        "  근거: 「지방계약법 시행령」 제25조제1항제5호가목, 「국가계약법 시행령」 제26조제1항제5호가목",
        "",
        "- **물품ㆍ용역 일반 기준**",
        "  - 일반 물품ㆍ용역: **추정가격 2천만원 이하**",
        "  - 소기업ㆍ소상공인, 여성기업, 장애인기업, 사회적기업 등 정책기업 요건에 해당하는 일부 물품ㆍ용역: **추정가격 1억원 이하** 범위의 수의계약 근거가 있습니다.",
        "  근거: 「지방계약법 시행령」 제25조제1항제5호, 「국가계약법 시행령」 제26조제1항제5호",
        "",
        "- **1인 견적 가능 기준은 별도입니다**",
        "  - 기본: **2천만원 이하**",
        "  - 청년창업기업ㆍ여성기업ㆍ장애인기업 등 일부 정책기업: **5천만원 이하**까지 1인 견적 가능 범위가 열립니다.",
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

    lines = [
        "맞습니다. **지역업체 가점ㆍ우대는 기관유형별로 같은 제도가 아닙니다.**",
        "소속기관을 먼저 확정한 뒤, 해당 기관의 낙찰자 결정기준과 입찰공고 기준으로 봐야 합니다.",
        "",
    ]

    if wants_local:
        lines += [
            "- **지방자치단체**",
            "  - 기술ㆍ학술용역 적격심사에는 `지역업체 참여도` 점수항목이 있습니다.",
            "  - 지역업체 합산 참여비율 **30% 이상: 3점**, **20% 이상 30% 미만: 1점**이 대표 기준입니다.",
            "  - 시설공사ㆍPQ 등에서는 지역업체 합산시공비율, 전문화 지역업체 참여도, 소규모 공사 접근성 가산 등으로 별도 평가될 수 있습니다.",
            "  근거: 「지방자치단체 입찰시 낙찰자 결정기준」",
            "",
        ]

    if wants_national:
        lines += [
            "- **국가기관**",
            "  - 국가계약법령 자체에 `모든 계약에 지역업체 가점 몇 점`처럼 일괄 적용되는 단일 점수표가 있는 구조는 아닙니다.",
            "  - 지역업체 우대는 주로 공동계약ㆍ지역업체 의무참여 또는 세부심사기준ㆍ입찰공고의 평가항목으로 나타납니다.",
            "  - 예를 들어 「국가계약법 시행령」 제72조와 「공동계약운용요령」 제9조는 일정 공동계약에서 지역업체 최소 지분율을 **30% 이상**, 사안에 따라 **40% 이상 또는 20% 이상**으로 두는 구조를 둡니다.",
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


def _regional_mandatory_joint_contract_answer() -> str:
    return "\n".join([
        "지역의무공동도급은 지역업체 참여를 강제해 지역 시공 참여를 확보하는 장치입니다. 핵심은 **공사에 한해** 적용한다는 점입니다.",
        "",
        "- **적용 대상**",
        "  - 지방계약에서 공동계약을 체결하는 경우, 지역경제 활성화를 위해 지역업체 참여비율을 정할 수 있습니다.",
        "  - 「지방자치단체 입찰 및 계약집행기준」은 **공사의 경우에만 지역의무 공동도급으로 발주할 수 있다**고 정합니다.",
        "  근거: 「지방계약법 시행령」 제88조, 「지방자치단체 입찰 및 계약집행기준」 공동계약 운영요령",
        "",
        "- **지역업체 최소 시공참여비율**",
        "  - 원칙: 해당 시ㆍ도 소재 지역업체의 최소 시공참여비율 **40%**를 입찰공고에 명시",
        "  - 지역경제 활성화 필요성이 있으면 **49% 이하의 범위**에서 정할 수 있습니다.",
        "",
        "- **발주하면 안 되거나 조정이 필요한 경우**",
        "  - 최소 참여비율 이상을 충족할 시공능력평가액을 갖춘 지역업체가 10인 미만인 경우",
        "  - 40% 이상 지역업체로 제한할 때 필요한 면허ㆍ등록 자격을 갖춘 지역업체가 10인 미만인 경우",
        "  - 품질 저하 우려나 공동수급체 구성이 곤란한 경우",
        "  - 지역업체 수를 과도하게 제한하거나 특정 지역업체 하도급ㆍ자재납품을 의무화하는 방식은 부당 제한이 될 수 있습니다.",
        "",
        "지역상품 구매 지원 관점에서는 대형 공사에서 부산 지역업체 참여를 제도적으로 확보하는 데 유용하지만, 입찰공고 단계에서 비율ㆍ면허ㆍ시공능력ㆍ업체 수를 먼저 확인해야 합니다.",
        "⚖️ 본 답변은 내부 DB에 적재된 법령ㆍ행정규칙 기준을 바탕으로 한 참고 안내입니다.",
    ])
