"""Procurement-domain intent normalization.

This module is intentionally rule-based and small.  It does not answer legal
questions; it translates common Korean procurement phrasing into stable signals
that the keyword router, Intent RAG resolver, and slot repair layer can share.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import re

try:
    from ..policies.item_normalization_policy import normalize_item_query
except Exception:  # Runtime path when app/ is on sys.path.
    from policies.item_normalization_policy import normalize_item_query


@dataclass(frozen=True)
class NormalizedIntentInput:
    original_text: str
    normalized_text: str
    compact_text: str
    amount: int | None = None
    amount_source: str = ""
    item_name: str = ""
    item_search_term: str = ""
    contract_object: str = ""
    contract_object_candidates: tuple[str, ...] = ()
    buyer_type: str = ""
    company_lookup_requested: bool = False
    company_lookup_blocked: bool = False
    company_lookup_only: bool = False
    local_support_requested: bool = False
    procedure_requested: bool = False
    procedure_blocked: bool = False
    contract_review_requested: bool = False
    interpretation_requested: bool = False
    legal_basis_requested: bool = False
    issue_tags: tuple[str, ...] = ()
    normalized_terms: tuple[str, ...] = ()
    reasons: tuple[str, ...] = field(default_factory=tuple)

    @property
    def search_text(self) -> str:
        additions = " ".join(self.normalized_terms)
        return f"{self.normalized_text} {additions}".strip()


def _compact(text: str) -> str:
    return re.sub(r"[\s\-_·ㆍ,]+", "", (text or "").lower())


def _has_any(compact_text: str, terms: tuple[str, ...]) -> bool:
    return any(_compact(term) in compact_text for term in terms)


def _append_unique(items: list[str], *values: str) -> None:
    for value in values:
        if value and value not in items:
            items.append(value)


_COMPANY_LOOKUP_NEGATIVE = (
    "업체추천필요없", "업체추천은필요없", "업체명추천필요없", "업체명은필요없",
    "업체명필요없", "업체후보필요없", "업체후보는필요없", "후보필요없",
    "후보는필요없", "목록필요없", "리스트필요없", "업체목록필요없",
    "업체리스트필요없", "후보는빼", "후보빼", "업체는빼", "업체빼",
    "업체명말고", "업체후보말고", "업체말고", "추천하지마", "추천은필요없",
    "검색하지마", "검색은필요없", "조회하지마", "조회는필요없",
)

_COMPANY_LOOKUP_FORCE = (
    "업체후보만", "기업후보만", "후보만", "업체만", "기업만",
    "업체목록만", "업체리스트만", "업체명만", "업체후보", "기업후보",
    "후보추천", "업체목록", "기업목록", "업체리스트", "기업리스트",
    "업체명", "공급업체", "납품업체", "등록업체", "조달등록업체",
)

_COMPANY_LOOKUP_HARD_FORCE = (
    "업체후보만", "기업후보만", "후보만", "업체만", "기업만",
    "업체목록만", "업체리스트만", "업체명만",
)

_COMPANY_SUBJECTS = ("업체", "기업", "공급사", "납품사", "부산업체", "지역업체")
_COMPANY_LOOKUP_VERBS = ("추천", "후보", "목록", "리스트", "찾아", "검색", "조회", "보여", "알려", "있어", "있나")
_COMPANY_STRATEGY_TERMS = (
    "방법", "제도", "검토", "참여", "활용", "우대", "가점", "지역제한",
    "공동도급", "계약하려면", "발주하려면", "가능한방법", "어떻게",
    "고를수", "선택", "선택가능", "사면", "살수", "구매경로", "계약경로",
    "구매방식", "계약방식",
)

_PROCEDURE_NEGATIVE = (
    "절차말고", "절차는빼", "절차빼", "절차필요없", "프로세스말고",
    "과정말고", "흐름말고",
)

_LOCAL_SUPPORT_TERMS = (
    "지역업체", "부산업체", "부산지역업체", "지역상품", "부산상품",
    "지역제품", "부산제품", "관내업체", "관내기업", "지역제한",
    "지역가점", "지역업체참여도", "지역의무공동도급", "의무공동도급",
    "부산소재", "지역기업",
)

_PROCEDURE_TERMS = ("절차", "흐름", "단계", "순서", "프로세스", "전체과정", "처리순서")

_CONTRACT_ACTION_TERMS = (
    "구매", "구입", "사려", "살건데", "사려고", "계약", "발주", "입찰",
    "수의", "견적", "납품", "용역", "공사", "계약방법", "구매방법",
    "진행", "추진",
)

_REVIEW_VERBS = ("가능", "방법", "검토", "안내", "어떻게", "해야", "하려고", "싶다", "되나", "될까", "해도")

_LEGAL_BASIS_TERMS = (
    "법령", "법률", "법적근거", "계약법", "지방계약법", "국가계약법",
    "판로지원법", "조달사업법", "시행령", "시행규칙", "예규", "고시",
    "근거", "조문", "규정",
)

_GOODS_OBJECT_TERMS = (
    "물품", "구매", "구입", "제품", "납품", "컴퓨터", "노트북", "cctv",
    "프린터", "가구", "조명", "서버", "장비", "기자재", "비품",
)

_SERVICE_OBJECT_TERMS = (
    "용역", "위탁", "대행", "청소", "경비", "유지보수", "시설관리",
    "컨설팅", "학술", "운영", "관리", "정비",
)

_CONSTRUCTION_OBJECT_TERMS = (
    "공사", "시공", "전기공사", "소방공사", "정보통신공사", "건설",
    "철거", "리모델링", "설치공사", "조경공사", "조경식재공사", "조경시설물공사",
)

_MIXED_OBJECT_PHRASES = (
    "납품설치", "설치포함", "구매설치", "납품및설치", "구매및설치",
    "구매유지관리", "유지보수포함", "장비구축", "시스템구축",
    "시스템도입", "도입운영", "장비설치", "관급자재", "공사에물품",
    "공사랑물품", "물품이랑공사", "납품시공",
)

_BUYER_TYPE_TERMS = {
    "national_agency": (
        "국가기관", "중앙행정기관", "중앙부처", "국가기관계약", "국가계약",
        "국가계약법", "조달청",
    ),
    "local_government": (
        "지방자치단체", "지자체", "부산시", "부산광역시", "시청", "구청",
        "군청", "지방계약", "지방계약법",
    ),
    "public_enterprise": (
        "공기업", "준정부기관", "공공기관", "지방공기업", "시설공단",
        "환경공단", "부산교통공사", "공단",
    ),
    "education_agency": (
        "교육청", "학교", "교육지원청",
    ),
}


def _parse_amount_won(text: str) -> tuple[int | None, str]:
    compact = _compact((text or "").replace(",", ""))
    if not compact:
        return None, ""

    # 4천5백만원, 1억4천5백만원처럼 '천/백 + 만원'이 섞인 표현.
    # 이 패턴을 먼저 보지 않으면 뒤의 일반 정규식이 "5백만원"만 잡아
    # 4천5백만원을 500만원으로 축소 해석할 수 있다.
    composite_man = re.search(
        r"(?:(\d+(?:\.\d+)?)억)?(?:(\d+(?:\.\d+)?)천)?(?:(\d+(?:\.\d+)?)백)?만원",
        compact,
    )
    if composite_man and any(composite_man.group(i) for i in (1, 2, 3)):
        total = 0.0
        if composite_man.group(1):
            total += float(composite_man.group(1)) * 100_000_000
        if composite_man.group(2):
            total += float(composite_man.group(2)) * 10_000_000
        if composite_man.group(3):
            total += float(composite_man.group(3)) * 1_000_000
        return int(total), "composite_korean_amount"

    # 1억5천만원, 1억5000만원, 1억5천
    mixed = re.search(r"(\d+(?:\.\d+)?)억(\d+(?:\.\d+)?)(천만원|천만|천|백만원|백만|만원|만)?", compact)
    if mixed:
        total = float(mixed.group(1)) * 100_000_000
        value = float(mixed.group(2))
        unit = mixed.group(3) or "천"
        if unit in ("천만원", "천만", "천"):
            total += value * 10_000_000
        elif unit in ("백만원", "백만"):
            total += value * 1_000_000
        elif unit in ("만원", "만"):
            total += value * 10_000
        return int(total), "mixed_korean_amount"

    explicit = re.search(r"(\d+(?:\.\d+)?)(억원|억|천만원|천만|백만원|백만|만원|만|원)", compact)
    if explicit:
        value = float(explicit.group(1))
        unit = explicit.group(2)
        if unit in ("억원", "억"):
            return int(value * 100_000_000), "explicit_amount"
        if unit in ("천만원", "천만"):
            return int(value * 10_000_000), "explicit_amount"
        if unit in ("백만원", "백만"):
            return int(value * 1_000_000), "explicit_amount"
        if unit in ("만원", "만"):
            return int(value * 10_000), "explicit_amount"
        return int(value), "explicit_amount"

    # Procurement users often abbreviate "예산 6천" as 6천만원.
    if _has_any(compact, ("예산", "금액", "추정가격", "기초금액", "사업비", "계약금액")):
        budget_short_composite = re.search(r"(\d+(?:\.\d+)?)천(\d+(?:\.\d+)?)백", compact)
        if budget_short_composite:
            return int(
                float(budget_short_composite.group(1)) * 10_000_000
                + float(budget_short_composite.group(2)) * 1_000_000
            ), "budget_short_composite_korean_amount"
        budget_short = re.search(r"(\d+(?:\.\d+)?)천(?:이고|으로|짜리|정도|규모|미만|이하|초과|이상)?", compact)
        if budget_short:
            return int(float(budget_short.group(1)) * 10_000_000), "budget_short_thousand_as_10m"

    plain_won = re.search(r"(\d{5,})원", compact)
    if plain_won:
        return int(plain_won.group(1)), "plain_won"

    return None, ""


def _infer_contract_object_candidates(compact: str, item_name: str) -> tuple[str, ...]:
    candidates: list[str] = []
    if item_name or _has_any(compact, _GOODS_OBJECT_TERMS):
        candidates.append("goods")
    if _has_any(compact, _SERVICE_OBJECT_TERMS):
        candidates.append("service")
    if _has_any(compact, _CONSTRUCTION_OBJECT_TERMS):
        candidates.append("construction")

    if _has_any(compact, _MIXED_OBJECT_PHRASES):
        if _has_any(compact, ("설치", "시공", "공사", "관급자재")):
            _append_unique(candidates, "goods", "construction")
        if _has_any(compact, ("유지관리", "유지보수", "운영", "관리")):
            _append_unique(candidates, "goods", "service")

    return tuple(dict.fromkeys(candidates))


def _infer_contract_object(compact: str, item_name: str) -> str:
    candidates = _infer_contract_object_candidates(compact, item_name)
    if "construction" in candidates:
        return "construction"
    if "service" in candidates:
        return "service"
    if "goods" in candidates:
        return "goods"
    return ""


def _detect_buyer_type(compact: str) -> tuple[str, tuple[str, ...]]:
    matched = [
        buyer_type
        for buyer_type, terms in _BUYER_TYPE_TERMS.items()
        if _has_any(compact, terms)
    ]
    matched = list(dict.fromkeys(matched))
    if len(matched) > 1:
        return "mixed", tuple(matched)
    if matched:
        return matched[0], tuple(matched)
    return "", tuple()


def _company_lookup_state(compact: str) -> tuple[bool, bool, bool, list[str]]:
    reasons: list[str] = []
    force = _has_any(compact, _COMPANY_LOOKUP_FORCE)
    hard_force = _has_any(compact, _COMPANY_LOOKUP_HARD_FORCE)
    negative = _has_any(compact, _COMPANY_LOOKUP_NEGATIVE) or bool(
        re.search(r"(업체명|업체추천|업체후보|후보|목록|리스트|업체검색|검색|조회)(?:은|는)?(?:필요없|빼|제외|말고|하지마)", compact)
    )
    if force:
        reasons.append("company_lookup_force_phrase")
    if negative:
        reasons.append("company_lookup_negative_phrase")

    has_subject = _has_any(compact, _COMPANY_SUBJECTS)
    has_lookup_verb = _has_any(compact, _COMPANY_LOOKUP_VERBS)
    has_strategy = _has_any(compact, _COMPANY_STRATEGY_TERMS)

    requested = force or (has_subject and has_lookup_verb and not has_strategy)
    blocked = negative and not hard_force
    lookup_only = force and _has_any(compact, ("만", "말고"))
    if blocked:
        requested = False
    return requested, blocked, lookup_only, reasons


@lru_cache(maxsize=512)
def normalize_query_intent(text: str) -> NormalizedIntentInput:
    original = text or ""
    normalized = re.sub(r"\s+", " ", original.strip())
    compact = _compact(normalized)
    reasons: list[str] = []
    terms: list[str] = []
    tags: list[str] = []

    amount, amount_source = _parse_amount_won(normalized)
    if amount is not None:
        reasons.append(f"amount_detected:{amount_source}")
        terms.append(f"{amount}원")

    item = normalize_item_query(normalized)
    item_name = item.canonical_name if item.found else ""
    item_search_term = item.primary_search_term if item.found else ""
    if item_name:
        reasons.append(f"item_alias:{item.matched_alias}")
        terms.append(item_name)
        if item_search_term and item_search_term != item_name:
            terms.append(item_search_term)

    contract_object_candidates = _infer_contract_object_candidates(compact, item_name)
    contract_object = _infer_contract_object(compact, item_name)
    if contract_object:
        terms.append(contract_object)

    buyer_type, buyer_type_candidates = _detect_buyer_type(compact)
    if buyer_type:
        terms.append(buyer_type)
        reasons.append(f"buyer_type:{buyer_type}")
    if len(buyer_type_candidates) > 1:
        _append_unique(tags, "agency_type_conflict")
        _append_unique(terms, "기관유형충돌")

    company_requested, company_blocked, company_only, company_reasons = _company_lookup_state(compact)
    reasons.extend(company_reasons)
    if company_requested:
        terms.append("업체후보조회")
    if company_blocked:
        terms.append("업체조회제외")

    local_support = _has_any(compact, _LOCAL_SUPPORT_TERMS)
    if local_support:
        terms.append("지역업체구매지원")
        reasons.append("local_support_phrase")

    procedure_blocked = _has_any(compact, _PROCEDURE_NEGATIVE)
    procedure = (
        _has_any(compact, _PROCEDURE_TERMS)
        and _has_any(compact, ("계약", "구매", "발주", "입찰", "물품", "용역", "공사"))
        and not procedure_blocked
    )
    if procedure:
        terms.append("계약절차")
        reasons.append("procedure_phrase")
    if procedure_blocked:
        terms.append("절차제외")
        reasons.append("procedure_negative_phrase")

    contract_review = (
        (amount is not None or _has_any(compact, ("예산", "금액", "추정가격", "예정가격", "기초금액")))
        and _has_any(compact, _CONTRACT_ACTION_TERMS)
        and _has_any(compact, _REVIEW_VERBS)
    )
    if contract_review:
        terms.append("계약방법검토")
        reasons.append("contract_review_phrase")

    if _has_any(compact, ("중소기업자간", "중기간", "경쟁제품", "직접생산", "직생")):
        _append_unique(tags, "sme_competition_product")
        _append_unique(terms, "중소기업자간경쟁제품", "직접생산확인")
    if _has_any(compact, ("소기업", "소상공인")) and _has_any(compact, ("1억미만", "1억원미만", "100000000원")):
        _append_unique(tags, "small_business_priority_procurement")
        _append_unique(terms, "소기업소상공인우선조달")
    if _has_any(compact, ("나눠발주", "나눠서발주", "쪼개서발주", "쪼개기", "분리발주", "분할발주")):
        _append_unique(tags, "split_procurement_review")
        _append_unique(terms, "분리발주", "쪼개기수의계약", "통합발주검토")
    if len(contract_object_candidates) >= 2 or _has_any(compact, _MIXED_OBJECT_PHRASES):
        _append_unique(tags, "mixed_contract_object")
        _append_unique(terms, "혼합계약대상")
    if _has_any(compact, ("공사기간늘", "공기가늘", "기간이늘", "기간늘", "공사기간연장", "공기연장")):
        _append_unique(tags, "construction_period_extension")
        _append_unique(terms, "공사기간연장", "공기연장")
    if _has_any(compact, ("간접비", "실비", "숙소비", "현장관리비")):
        _append_unique(tags, "indirect_cost_review")
        _append_unique(terms, "간접비", "실비정산")
    if _has_any(compact, ("자동연장", "계약기간연장", "특별한사유", "신규비목", "계약금액조정", "설계변경")):
        _append_unique(tags, "practice_interpretation_case")

    interpretation = bool(
        set(tags)
        & {
            "construction_period_extension",
            "indirect_cost_review",
            "practice_interpretation_case",
            "split_procurement_review",
        }
    ) or _has_any(compact, ("해석사례", "질의회신", "질의", "회신", "판단", "가능여부"))

    legal_basis = _has_any(compact, _LEGAL_BASIS_TERMS)
    if legal_basis:
        terms.append("법적근거")

    return NormalizedIntentInput(
        original_text=original,
        normalized_text=normalized,
        compact_text=compact,
        amount=amount,
        amount_source=amount_source,
        item_name=item_name,
        item_search_term=item_search_term,
        contract_object=contract_object,
        contract_object_candidates=contract_object_candidates,
        buyer_type=buyer_type,
        company_lookup_requested=company_requested,
        company_lookup_blocked=company_blocked,
        company_lookup_only=company_only,
        local_support_requested=local_support,
        procedure_requested=procedure,
        procedure_blocked=procedure_blocked,
        contract_review_requested=contract_review,
        interpretation_requested=interpretation,
        legal_basis_requested=legal_basis,
        issue_tags=tuple(tags),
        normalized_terms=tuple(dict.fromkeys(terms)),
        reasons=tuple(dict.fromkeys(reasons)),
    )
