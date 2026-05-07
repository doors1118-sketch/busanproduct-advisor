"""
내부 법령 DB 조회 모듈 (Internal Law Lookup)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MCP preflight 및 LLM 도구 호출 시 외부 법제처 API 대신
내부 DB를 우선 조회하고, 내부 DB에 없을 때만 외부 MCP를 보완적으로 호출.

내부 데이터 소스:
  1. key_articles.json — 핵심 조문 원문 (7종, 27,271자)
  2. ChromaDB laws — 법령 벡터 임베딩 (13개 법령, ~800+ 조문)
  3. legal_db_v0_1_3.sqlite — 법령 소스 메타데이터 (217건)

조회 우선순위:
  key_articles (정확한 조문 매칭) → ChromaDB (의미 검색) → 외부 MCP (보완)
"""
import os
import re
import json
from typing import Optional

_ROOT = os.path.dirname(os.path.abspath(__file__))
_KEY_ARTICLES_PATH = os.path.join(_ROOT, "data", "key_articles.json")

# ─────────────────────────────────────────────
# key_articles.json 로딩 (1회 캐싱)
# ─────────────────────────────────────────────
_key_articles_cache: dict = None

def _load_key_articles() -> dict:
    global _key_articles_cache
    if _key_articles_cache is not None:
        return _key_articles_cache
    try:
        with open(_KEY_ARTICLES_PATH, "r", encoding="utf-8") as f:
            _key_articles_cache = json.load(f)
        print(f"  [INTERNAL_LAW] key_articles.json 로드: {len(_key_articles_cache)} entries")
    except Exception as e:
        print(f"  [INTERNAL_LAW] key_articles.json 로드 실패: {e}")
        _key_articles_cache = {}
    return _key_articles_cache


# ─────────────────────────────────────────────
# 조문번호 추출 + 법령명 매칭
# ─────────────────────────────────────────────
# 쿼리에서 "제25조", "제9조" 등 조문번호와 법령 약칭을 추출하여
# key_articles.json의 값(원문 텍스트)에서 매칭

# key_articles 키 → 법령명+조문 매핑 (수동 정의)
_KEY_ARTICLE_INDEX = {
    # 지방계약법 시행령
    "제25조": ["R_DIRECT_GENERAL_SMALL_AMOUNT", "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY"],
    "제30조": [],  # key_articles에 없음 — ChromaDB 또는 외부 MCP로 fallback
    "제88조": ["R_LOCAL_REGIONAL_JOINT_CONTRACT"],
    "제20조": ["R_REGIONAL_RESTRICTION_GOODS", "R_REGIONAL_RESTRICTION_SERVICE", "R_REGIONAL_RESTRICTION_CONSTRUCTION"],
    # 국가계약법 시행령
    "제72조": ["R_NATIONAL_REGIONAL_JOINT_CONTRACT"],
}

# 법령명 약칭 → 매칭 키워드
_LAW_NAME_PATTERNS = {
    "지방계약법": ["지방계약법", "지방자치단체를 당사자로 하는"],
    "국가계약법": ["국가계약법", "국가를 당사자로 하는"],
    "중소기업구매촉진법": ["중소기업제품 구매촉진", "중소기업구매촉진"],
    "조달사업법": ["조달사업에 관한"],
}


def search_internal_law(query: str) -> Optional[str]:
    """
    내부 DB에서 법령 조문 검색.
    
    Returns:
        조문 원문 텍스트 (찾으면) 또는 None (못 찾으면 → 외부 MCP로 fallback)
    """
    # 1단계: key_articles.json에서 정확 매칭
    result = _search_key_articles(query)
    if result:
        return result
    
    # 2단계: ChromaDB(ingest_laws)에서 의미 검색
    result = _search_chromadb_laws(query)
    if result:
        return result
    
    # 3단계: 내부에 없음 → None 반환 (호출자가 외부 MCP로 fallback)
    return None


def _search_key_articles(query: str) -> Optional[str]:
    """key_articles.json에서 조문번호 기반 정확 매칭."""
    ka = _load_key_articles()
    if not ka:
        return None
    
    # 쿼리에서 조문번호 추출 (예: "지방계약법 시행령 제25조" → "제25조")
    article_match = re.search(r"제(\d+)조", query)
    if not article_match:
        return None
    
    article_key = f"제{article_match.group(1)}조"
    candidate_keys = _KEY_ARTICLE_INDEX.get(article_key, [])
    
    if not candidate_keys:
        return None
    
    # 법령명으로 필터링
    query_lower = query.lower()
    for ka_key in candidate_keys:
        text = ka.get(ka_key, "")
        if not text:
            continue
        
        # 지방계약법 관련 쿼리면 지방계약법 조문만 반환
        if "지방계약법" in query or "지방" in query:
            if "지방" in text[:50] or "R_LOCAL" in ka_key or "R_DIRECT" in ka_key or "R_REGIONAL" in ka_key:
                print(f"  [INTERNAL_LAW] key_articles HIT: {ka_key} ({len(text)} chars)")
                return f"[내부DB] {text}"
        
        # 국가계약법 관련 쿼리
        if "국가계약법" in query or "국가" in query:
            if "국가" in text[:50] or "R_NATIONAL" in ka_key:
                print(f"  [INTERNAL_LAW] key_articles HIT: {ka_key} ({len(text)} chars)")
                return f"[내부DB] {text}"
        
        # 일반 매칭 (법령명 불특정)
        if article_key in text:
            print(f"  [INTERNAL_LAW] key_articles HIT (general): {ka_key} ({len(text)} chars)")
            return f"[내부DB] {text}"
    
    return None


def _search_chromadb_laws(query: str, n_results: int = 3) -> Optional[str]:
    """ChromaDB laws 컬렉션에서 벡터+BM25 하이브리드 검색."""
    try:
        from ingest_laws import search_laws
        results = search_laws(query, n_results=n_results)
        
        if not results:
            return None
        
        lines = []
        for i, r in enumerate(results):
            law = r.get("law", "?")
            article = r.get("article", "?")
            title = r.get("title", "?")
            text = r.get("text", "")
            lines.append(f"[내부DB 검색 #{i+1}] [{law}] {article} {title}")
            lines.append(text[:800])
            lines.append("")
        
        combined = "\n".join(lines)
        if len(combined.strip()) > 50:
            print(f"  [INTERNAL_LAW] ChromaDB HIT: {len(results)} results ({len(combined)} chars)")
            return combined
    except Exception as e:
        print(f"  [INTERNAL_LAW] ChromaDB 검색 실패: {e}")
    
    return None


def search_internal_admin_rule(query: str) -> Optional[str]:
    """내부 DB에서 행정규칙 검색. (현재는 미구현 → None 반환 → 외부 MCP로 fallback)"""
    # TODO: 향후 행정규칙 내부 DB 구축 시 구현
    return None
