"""
Guardrail Sanity Check — 최종 보정
"""
import re


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


def _has_any(q: str, terms: tuple[str, ...]) -> bool:
    return any(term in q for term in terms)


def _is_explicit_company_lookup(question: str) -> bool:
    q = _compact(question)
    if not q:
        return False

    company_lookup_terms = (
        "업체추천", "기업추천", "업체후보", "기업후보", "후보추천",
        "업체목록", "기업목록", "업체리스트", "기업리스트", "업체명",
        "업체있", "기업있", "있는업체", "있는기업",
        "공급업체", "납품업체", "등록업체", "조달등록업체",
    )
    if _has_any(q, company_lookup_terms):
        return True

    has_company_subject = _has_any(q, ("업체", "기업", "공급사", "납품사"))
    has_lookup_verb = _has_any(q, (
        "추천", "후보", "목록", "리스트", "찾아", "검색", "조회", "보여", "알려", "있어",
    ))
    strategy_terms = (
        "방법", "제도", "검토", "참여", "활용", "우대", "가점", "지역제한",
        "공동도급", "계약하려면", "발주하려면", "가능한방법", "어떻게",
    )
    return has_company_subject and has_lookup_verb and not _has_any(q, strategy_terms)


def _has_local_support_context(question: str) -> bool:
    q = _compact(question)
    return _has_any(q, (
        "지역업체", "부산업체", "부산지역업체", "지역업체참여",
        "지역업체활용", "지역업체우대", "지역상품", "부산상품",
        "지역제품", "부산제품", "관내업체", "관내기업", "지역제한",
        "지역가점", "지역업체참여도", "지역의무공동도급", "의무공동도급",
    ))


def apply_guardrail_sanity_check(
    question: str,
    selected: list[str],
) -> list[str]:
    """질문 내용 기반으로 누락 가드레일 보정"""
    final = set(selected)
    q = question.lower()
    is_definition_query = any(kw in q for kw in [
        "정의", "뜻", "의미", "무슨 말", "무엇", "뭐야", "요건", "기준"
    ]) and any(kw in q for kw in [
        "법", "시행령", "시행규칙", "예규", "고시", "훈령", "조례",
        "계약집행기준", "낙찰자 결정기준", "조문", "제"
    ])

    explicit_company_lookup = _is_explicit_company_lookup(question)
    has_local_support_context = _has_local_support_context(question)

    # 업체 후보/목록을 실제로 요청한 경우에만 company_search 보정
    if not is_definition_query and explicit_company_lookup:
        final.add("company_search")
    elif has_local_support_context:
        final.discard("company_search")
        final.add("common_procurement")

    # 공사+물품 혼합 → mixed_contract 보정
    has_construction = any(kw in q for kw in ["공사", "시공", "철거"])
    has_item = any(kw in q for kw in ["물품", "구매", "장비", "납품"])
    has_service = any(kw in q for kw in ["용역", "대행", "위탁"])

    mixed_count = sum([has_construction, has_item, has_service])
    if mixed_count >= 2:
        final.add("mixed_contract")

    # 금액 포함 → common_procurement 보정 (금액 판단 필수)
    if re.search(r"\d+\s*(만원|억|원|백만)", q):
        final.add("common_procurement")

    # 수의계약 키워드 → common_procurement 보정
    if any(kw in q for kw in ["수의계약", "1인 견적", "견적"]):
        final.add("common_procurement")

    # 개별 계약유형 추가 보정 (P0-2)
    if has_construction:
        final.add("construction_contract")
    if has_service:
        final.add("service_contract")
    if has_item:
        final.add("item_purchase")
    if any(kw in q for kw in ["mas", "종합쇼핑몰", "쇼핑몰", "다수공급자"]):
        final.add("mas_shopping_mall")

    if is_definition_query:
        final.discard("company_search")

    return sorted(final)
