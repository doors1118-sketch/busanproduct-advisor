"""
내부 법령 DB 조회 모듈 (Internal Law Lookup)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MCP preflight 및 LLM 도구 호출 시 외부 법제처 API 대신
내부 DB를 우선 조회하고, 내부 DB에 없을 때만 외부 MCP를 보완적으로 호출.

내부 데이터 소스:
  1. law_articles_db.json — 13종 핵심 법령 전체 조문 (243개 조문, 73,696자)
  2. key_articles.json — 레거시 핵심 조문 (7종, 보완용)

조회 흐름:
  law_articles_db.json (조문번호 매칭) → key_articles.json (보완) → 외부 MCP (fallback)
"""
import os
import re
import json
from typing import Optional

_ROOT = os.path.dirname(os.path.abspath(__file__))
_LAW_DB_PATH = os.path.join(_ROOT, "data", "law_articles_db.json")
_KEY_ARTICLES_PATH = os.path.join(_ROOT, "data", "key_articles.json")

# ─────────────────────────────────────────────
# DB 로딩 (1회 캐싱)
# ─────────────────────────────────────────────
_law_db_cache: dict = None
_key_articles_cache: dict = None
# 빠른 조회용 인덱스: "지방계약법 시행령 제25조" → 조문 텍스트
_lookup_index: dict = None


def _load_law_db() -> dict:
    global _law_db_cache, _lookup_index
    if _law_db_cache is not None:
        return _law_db_cache
    try:
        with open(_LAW_DB_PATH, "r", encoding="utf-8") as f:
            _law_db_cache = json.load(f)
        # 조회용 인덱스 구축
        _lookup_index = {}
        total_articles = 0
        for short_name, law_data in _law_db_cache.items():
            articles = law_data.get("articles", {})
            for article_no, article_data in articles.items():
                # "지방계약법 시행령 제25조" → 조문 텍스트
                lookup_key = f"{short_name} {article_no}"
                _lookup_index[lookup_key] = article_data.get("text", "")
                total_articles += 1
        print(f"  [INTERNAL_LAW] law_articles_db.json 로드: {len(_law_db_cache)}개 법령, {total_articles}개 조문")
    except Exception as e:
        print(f"  [INTERNAL_LAW] law_articles_db.json 로드 실패: {e}")
        _law_db_cache = {}
        _lookup_index = {}
    return _law_db_cache


def _load_key_articles() -> dict:
    global _key_articles_cache
    if _key_articles_cache is not None:
        return _key_articles_cache
    try:
        with open(_KEY_ARTICLES_PATH, "r", encoding="utf-8") as f:
            _key_articles_cache = json.load(f)
    except Exception:
        _key_articles_cache = {}
    return _key_articles_cache


# ─────────────────────────────────────────────
# 법령 약칭 매핑 (쿼리에서 약칭 추출용)
# ─────────────────────────────────────────────
_SHORT_NAME_MAP = {
    "지방계약법 시행규칙": "지방계약법 시행규칙",
    "지방계약법 시행령": "지방계약법 시행령",
    "지방계약법": "지방계약법",
    "국가계약법 시행규칙": "국가계약법 시행규칙",
    "국가계약법 시행령": "국가계약법 시행령",
    "국가계약법": "국가계약법",
    "중소기업구매촉진법 시행규칙": "중소기업구매촉진법 시행규칙",
    "중소기업구매촉진법 시행령": "중소기업구매촉진법 시행령",
    "중소기업구매촉진법": "중소기업구매촉진법",
    "조달사업법 시행규칙": "조달사업법 시행규칙",
    "조달사업법 시행령": "조달사업법 시행령",
    "조달사업법": "조달사업법",
    "공기업계약사무규칙": "공기업계약사무규칙",
    "계약사무규칙": "공기업계약사무규칙",
}


def _extract_law_and_article(query: str):
    """쿼리에서 법령 약칭 + 조문번호 추출."""
    # 조문번호 추출
    article_match = re.search(r"(제\d+조(?:의\d+)?)", query)
    article_no = article_match.group(1) if article_match else None
    
    # 법령 약칭 추출 (긴 것부터 매칭)
    matched_short = None
    for pattern in sorted(_SHORT_NAME_MAP.keys(), key=len, reverse=True):
        if pattern in query:
            matched_short = _SHORT_NAME_MAP[pattern]
            break
    
    return matched_short, article_no


# ─────────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────────

def search_internal_law(query: str) -> Optional[str]:
    """
    내부 DB에서 법령 조문 검색.
    
    Returns:
        조문 원문 텍스트 (찾으면) 또는 None (못 찾으면 → 외부 MCP로 fallback)
    """
    _load_law_db()
    
    # 1단계: law_articles_db.json에서 정확 매칭
    result = _search_law_db(query)
    if result:
        return result
    
    # 2단계: key_articles.json (레거시 보완)
    result = _search_key_articles(query)
    if result:
        return result
    
    # 3단계: 내부에 없음 → None 반환 (호출자가 외부 MCP로 fallback)
    return None


def _search_law_db(query: str) -> Optional[str]:
    """law_articles_db.json에서 법령 약칭 + 조문번호로 정확 매칭."""
    if not _lookup_index:
        return None
    
    short_name, article_no = _extract_law_and_article(query)
    
    if short_name and article_no:
        # 정확 매칭: "지방계약법 시행령 제25조"
        lookup_key = f"{short_name} {article_no}"
        text = _lookup_index.get(lookup_key)
        if text and len(text) > 10:
            print(f"  [INTERNAL_LAW] law_db HIT: {lookup_key} ({len(text)} chars)")
            return f"[내부DB] [{lookup_key}]\n{text}"
    
    if short_name and not article_no:
        # 법령명만 있고 조문번호 없음 → 해당 법령의 전체 조문 목록 반환
        db = _law_db_cache or {}
        law_data = db.get(short_name)
        if law_data:
            articles = law_data.get("articles", {})
            lines = [f"[내부DB] {short_name} 전체 조문 목록 ({len(articles)}개):"]
            for art_no, art_data in list(articles.items())[:20]:
                title = art_data.get("title", "")
                text_preview = art_data.get("text", "")[:100]
                lines.append(f"  {art_no} {title}: {text_preview}...")
            result = "\n".join(lines)
            print(f"  [INTERNAL_LAW] law_db HIT (목록): {short_name} ({len(articles)} articles)")
            return result
    
    # 키워드 기반 검색 (조문번호 없이 내용으로 검색)
    if not article_no and _lookup_index:
        query_keywords = set(query.replace(" ", ""))
        best_match = None
        best_score = 0
        for key, text in _lookup_index.items():
            # 쿼리 키워드가 조문 텍스트에 포함되는 비율
            score = sum(1 for kw in query_keywords if kw in text[:500])
            if score > best_score and score >= 3:
                best_score = score
                best_match = (key, text)
        
        if best_match:
            key, text = best_match
            print(f"  [INTERNAL_LAW] law_db HIT (keyword): {key} (score={best_score})")
            return f"[내부DB] [{key}]\n{text}"
    
    return None


def _search_key_articles(query: str) -> Optional[str]:
    """key_articles.json에서 레거시 매칭 (보완용)."""
    ka = _load_key_articles()
    if not ka:
        return None
    
    article_match = re.search(r"제(\d+)조", query)
    if not article_match:
        return None
    
    article_no = f"제{article_match.group(1)}조"
    
    for ka_key, text in ka.items():
        if article_no in text[:200]:
            if "지방" in query and ("지방" in text[:80] or "R_LOCAL" in ka_key or "R_DIRECT" in ka_key or "R_REGIONAL" in ka_key):
                print(f"  [INTERNAL_LAW] key_articles HIT: {ka_key}")
                return f"[내부DB] {text}"
            if "국가" in query and ("국가" in text[:80] or "R_NATIONAL" in ka_key):
                print(f"  [INTERNAL_LAW] key_articles HIT: {ka_key}")
                return f"[내부DB] {text}"
    
    return None


def search_internal_admin_rule(query: str) -> Optional[str]:
    """내부 DB에서 행정규칙 검색. (현재 미구현 → None → 외부 MCP fallback)"""
    # TODO: 향후 행정규칙 내부 DB 구축 시 구현
    return None
