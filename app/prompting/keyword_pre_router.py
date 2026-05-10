"""
Keyword Pre-Router — 키워드 매칭 기반 1차 분류
"""
import os
import re
from .schemas import KeywordRouteResult

try:
    from app.router.intent_normalization import normalize_query_intent
except Exception:  # Runtime path when app/ is on sys.path.
    try:
        from router.intent_normalization import normalize_query_intent
    except Exception:
        normalize_query_intent = None

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_YAML_PATH = os.path.join(_BASE_DIR, "config", "keyword_routes.yaml")

# ─── 키워드 맵 로드 ───
_keyword_map: dict = {}
_ambiguous_keywords: list = []

def _load_keyword_map():
    global _keyword_map, _ambiguous_keywords
    if _keyword_map:
        return
    try:
        import yaml
        with open(_YAML_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _ambiguous_keywords = data.pop("ambiguous_keywords", [])
        _keyword_map = data
    except Exception:
        # Fallback 하드코딩
        _keyword_map = {
            "construction_contract": ["공사", "시공", "철거", "건설", "하도급"],
            "service_contract": ["용역", "대행", "컨설팅", "위탁", "과업"],
            "item_purchase": ["물품", "구매", "납품", "장비", "컴퓨터", "제품"],
            "mas_shopping_mall": ["종합쇼핑몰", "MAS", "다수공급자계약", "2단계 경쟁"],
            "company_search": ["업체", "부산 업체", "지역업체", "추천"],
        }
        _ambiguous_keywords = [
            "사업", "조성", "조성사업", "개선", "정비", "운영",
            "유지관리", "구축", "설치", "시스템 구축", "설치 포함",
        ]
    try:
        try:
            from policies.procurement_router_lexicon import merge_keyword_route_extensions
        except ImportError:
            from importlib import import_module

            merge_keyword_route_extensions = import_module(
                "app.policies.procurement_router_lexicon"
            ).merge_keyword_route_extensions
        _keyword_map, _ambiguous_keywords = merge_keyword_route_extensions(_keyword_map, _ambiguous_keywords)
    except Exception:
        pass


def _compact(text: str) -> str:
    return (text or "").replace(" ", "").lower()


def _has_any(q: str, terms: tuple[str, ...]) -> bool:
    return any(term in q for term in terms)


def _is_explicit_company_lookup(question: str) -> bool:
    """업체 후보/목록 조회를 실제로 요청한 경우만 True."""
    if normalize_query_intent is not None:
        norm = normalize_query_intent(question)
        return norm.company_lookup_requested and not norm.company_lookup_blocked

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
    strategy_terms = (
        "방법", "제도", "검토", "참여", "활용", "우대", "가점", "지역제한",
        "공동도급", "계약하려면", "발주하려면", "가능한방법", "어떻게",
    )
    has_lookup_verb = _has_any(q, (
        "추천", "후보", "목록", "리스트", "찾아", "검색", "조회", "보여", "알려", "있어",
    ))
    return has_company_subject and has_lookup_verb and not _has_any(q, strategy_terms)


def _has_local_support_context(question: str) -> bool:
    if normalize_query_intent is not None:
        return normalize_query_intent(question).local_support_requested
    q = _compact(question)
    return _has_any(q, (
        "지역업체", "부산업체", "부산지역업체", "지역업체참여",
        "지역업체활용", "지역업체우대", "지역상품", "부산상품",
        "지역제품", "부산제품", "관내업체", "관내기업", "지역제한",
        "지역가점", "지역업체참여도", "지역의무공동도급", "의무공동도급",
    ))


def _has_contract_review_context(question: str) -> bool:
    if normalize_query_intent is not None:
        return normalize_query_intent(question).contract_review_requested
    q = _compact(question)
    has_amount = bool(re.search(r"\d+(?:\.\d+)?\s*(?:억원|억|천만원|백만원|만원|원)", question or ""))
    has_budget = _has_any(q, ("예산", "금액", "추정가격", "예정가격", "기초금액"))
    has_object_or_action = _has_any(q, (
        "구매", "계약", "발주", "입찰", "수의", "견적", "물품", "용역",
        "공사", "납품", "제조", "설치", "과업", "계약방법", "구매방법",
    ))
    has_review_verb = _has_any(q, ("가능", "방법", "검토", "안내", "어떻게", "해야", "잡아야"))
    return (has_amount or has_budget) and has_object_or_action and has_review_verb


def keyword_pre_route(question: str) -> KeywordRouteResult:
    """키워드 기반 1차 라우팅"""
    _load_keyword_map()

    q = question.lower()
    explicit_company_lookup = _is_explicit_company_lookup(question)
    local_support_context = _has_local_support_context(question)
    contract_review_context = _has_contract_review_context(question)
    matched = []
    forced = []
    ambiguous = []

    # 다의어 체크
    for kw in _ambiguous_keywords:
        if kw in q:
            ambiguous.append(kw)

    # 카테고리 매칭
    for category, keywords in _keyword_map.items():
        for kw in keywords:
            if kw.lower() in q:
                if category not in matched:
                    matched.append(category)
                break

    # "지역업체 참여 방법"은 업체 후보 조회가 아니라 지역구매지원 제도 검토다.
    if "company_search" in matched and not explicit_company_lookup:
        matched = [category for category in matched if category != "company_search"]

    if local_support_context and "local_purchase_support" not in matched:
        matched.append("local_purchase_support")

    if contract_review_context and "contract_review" not in matched:
        matched.append("contract_review")

    if explicit_company_lookup and "company_search" not in matched:
        matched.append("company_search")

    # company_search는 실제 후보/목록 요청일 때만 forced guardrail로 추가
    if "company_search" in matched and explicit_company_lookup:
        forced.append("company_search")

    # is_unambiguous 판정: fast path 조건
    # 단일 유형 + 다의어 없음 + mixed_contract 키워드 없음
    is_unambiguous = (
        len(matched) == 1
        and len(ambiguous) == 0
        and matched[0] in ("item_purchase", "service_contract",
                           "construction_contract", "mas_shopping_mall",
                           "company_search", "policy_candidate_search",
                           "certified_product_search", "shopping_mall_search",
                           "company_detail")
    )
    if matched == ["company_search"] and not explicit_company_lookup:
        is_unambiguous = False

    # 다의어 있으면 mixed_contract 후보 추가
    if ambiguous and "mixed_contract" not in matched:
        matched.append("mixed_contract")

    # 매칭 없으면 unclear
    if not matched:
        matched.append("unclear")

    return KeywordRouteResult(
        matched_categories=matched,
        forced_guardrails=forced,
        ambiguous_keywords=ambiguous,
        is_unambiguous=is_unambiguous,
    )
