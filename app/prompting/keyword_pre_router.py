"""
Keyword Pre-Router — 키워드 매칭 기반 1차 분류
"""
import os
from .schemas import KeywordRouteResult

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


def keyword_pre_route(question: str) -> KeywordRouteResult:
    """키워드 기반 1차 라우팅"""
    _load_keyword_map()

    q = question.lower()
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

    # company_search가 매칭되면 forced guardrail로 추가
    if "company_search" in matched:
        forced.append("company_search")

    # is_unambiguous 판정: fast path 조건
    # 단일 유형 + 다의어 없음 + mixed_contract 키워드 없음
    is_unambiguous = (
        len(matched) == 1
        and len(ambiguous) == 0
        and matched[0] in ("item_purchase", "service_contract",
                           "construction_contract", "mas_shopping_mall")
    )

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
