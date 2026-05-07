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
    """내부 DB에서 행정규칙 검색."""
    _load_law_db()
    if not _law_db_cache:
        return None
    
    # 행정규칙명 직접 매칭
    for short_name, law_data in _law_db_cache.items():
        source = law_data.get("source", "")
        if "행정규칙" not in source and "예규" not in short_name and "규정" not in short_name \
           and "요령" not in short_name and "기준" not in short_name and "유의서" not in short_name \
           and "세칙" not in short_name and "내역" not in short_name:
            continue
        # 쿼리 키워드가 행정규칙명에 포함되는지
        query_clean = query.replace(" ", "").replace("·", "")
        name_clean = short_name.replace(" ", "").replace("·", "")
        if query_clean in name_clean or name_clean in query_clean:
            articles = law_data.get("articles", {})
            lines = [f"[내부DB] {short_name}"]
            for art_no, art_data in list(articles.items())[:5]:
                lines.append(art_data.get("text", "")[:2000])
            result = "\n".join(lines)
            print(f"  [INTERNAL_LAW] admin_rule HIT: {short_name} ({len(result)} chars)")
            return result
    
    # 키워드 검색
    query_chars = set(query.replace(" ", ""))
    best = None
    best_score = 0
    for short_name, law_data in _law_db_cache.items():
        source = law_data.get("source", "")
        if "행정규칙" not in source and "예규" not in short_name and "규정" not in short_name:
            continue
        articles = law_data.get("articles", {})
        for art_no, art_data in articles.items():
            text = art_data.get("text", "")
            score = sum(1 for c in query_chars if c in text[:1000])
            if score > best_score and score >= 5:
                best_score = score
                best = (short_name, text)
    
    if best:
        name, text = best
        print(f"  [INTERNAL_LAW] admin_rule HIT (keyword): {name} (score={best_score})")
        return f"[내부DB] [{name}]\n{text[:3000]}"
    
    return None


# ─────────────────────────────────────────────
# 법체계 매핑: 법률 → 시행령 → 시행규칙 → 관련 행정규칙
# ─────────────────────────────────────────────
_LAW_SYSTEM_MAP = {
    "지방계약법": {
        "법률": "지방계약법",
        "시행령": "지방계약법 시행령",
        "시행규칙": "지방계약법 시행규칙",
        "행정규칙": [
            "지방자치단체 입찰 및 계약집행기준",
            "지방자치단체 입찰시 낙찰자 결정기준",
        ],
    },
    "국가계약법": {
        "법률": "국가계약법",
        "시행령": "국가계약법 시행령",
        "시행규칙": "국가계약법 시행규칙",
        "행정규칙": [
            "(계약예규) 정부 입찰·계약 집행기준",
            "(계약예규) 공동계약운용요령",
            "(계약예규) 공사계약일반조건",
            "(계약예규) 용역계약일반조건",
            "(계약예규) 종합계약집행요령",
            "(계약예규) 용역입찰유의서",
        ],
    },
    "중소기업구매촉진법": {
        "법률": "중소기업구매촉진법",
        "시행령": "중소기업구매촉진법 시행령",
        "시행규칙": "중소기업구매촉진법 시행규칙",
        "행정규칙": [
            "중소기업자간 경쟁제품 및 공사용자재 직접구매 대상 품목 지정 내역",
            "중소기업기술개발제품 우선구매제도 운영 등에 관한 시행세칙",
        ],
    },
    "조달사업법": {
        "법률": "조달사업법",
        "시행령": "조달사업법 시행령",
        "시행규칙": "조달사업법 시행규칙",
        "행정규칙": [
            "물품 다수공급자계약 업무처리규정",
            "국가종합전자조달시스템 종합쇼핑몰 운영규정",
            "우수조달공동상표 물품 지정 관리규정",
            "조달청 제조물품 직접생산확인 기준",
            "혁신제품 구매 운영 규정",
        ],
    },
    "공기업계약": {
        "법률": None,
        "시행령": None,
        "시행규칙": "공기업계약사무규칙",
        "행정규칙": [
            "기타공공기관 계약사무 운영규정",
        ],
    },
}


def _detect_law_system(query: str) -> str:
    """쿼리에서 법체계 계열 감지."""
    if "지방계약법" in query or "지방자치단체" in query or "지방" in query:
        return "지방계약법"
    if "국가계약법" in query or "국가를 당사자" in query:
        return "국가계약법"
    if "중소기업" in query or "구매촉진" in query or "판로" in query:
        return "중소기업구매촉진법"
    if "조달" in query or "나라장터" in query or "MAS" in query or "다수공급자" in query:
        return "조달사업법"
    if "공기업" in query or "준정부" in query or "공공기관" in query:
        return "공기업계약"
    # 기본: 수의계약/입찰 등 일반 키워드 → 지방계약법 (가장 빈번)
    return "지방계약법"


def _get_relevant_articles(law_short: str, query: str, max_articles: int = 5) -> list:
    """해당 법령에서 쿼리와 관련된 핵심 조문 추출."""
    db = _law_db_cache or {}
    law_data = db.get(law_short)
    if not law_data:
        return []
    
    articles = law_data.get("articles", {})
    if not articles:
        return []
    
    query_chars = set(query.replace(" ", ""))
    scored = []
    for art_no, art_data in articles.items():
        text = art_data.get("text", "")
        title = art_data.get("title", "")
        # 점수: 쿼리 키워드와 조문 텍스트의 매칭도
        score = sum(1 for c in query_chars if c in (text[:500] + title))
        scored.append((score, art_no, title, text))
    
    scored.sort(reverse=True)
    return [(no, title, text) for _, no, title, text in scored[:max_articles] if _ >= 2]


def chain_law_system_internal(query: str) -> Optional[str]:
    """
    내부 DB 전용 — 법률→시행령→시행규칙→행정규칙 4단 체계 분석.
    
    외부 MCP 호출 없이 0ms 수준으로 작동.
    """
    _load_law_db()
    if not _law_db_cache:
        return None
    
    system_key = _detect_law_system(query)
    system = _LAW_SYSTEM_MAP.get(system_key)
    if not system:
        return None
    
    lines = [f"═══ 법체계 분석 (내부DB): {system_key} ═══", ""]
    total_found = 0
    
    # 4단계 순회
    for tier_name in ["법률", "시행령", "시행규칙"]:
        law_short = system.get(tier_name)
        if not law_short:
            continue
        
        relevant = _get_relevant_articles(law_short, query, max_articles=3)
        if relevant:
            lines.append(f"▶ {tier_name}: {law_short}")
            for art_no, title, text in relevant:
                title_str = f" ({title})" if title else ""
                lines.append(f"  {art_no}{title_str}")
                lines.append(f"  {text[:800]}")
                lines.append("")
                total_found += 1
        else:
            lines.append(f"▶ {tier_name}: {law_short} (관련 조문 없음)")
            lines.append("")
    
    # 행정규칙
    admin_rules = system.get("행정규칙", [])
    if admin_rules:
        lines.append("▶ 관련 행정규칙:")
        for rule_name in admin_rules:
            rule_data = _law_db_cache.get(rule_name)
            if rule_data:
                articles = rule_data.get("articles", {})
                first_text = ""
                for art_data in list(articles.values())[:1]:
                    first_text = art_data.get("text", "")[:500]
                lines.append(f"  ● {rule_name}")
                if first_text:
                    lines.append(f"    {first_text}")
                lines.append("")
                total_found += 1
    
    if total_found == 0:
        return None
    
    result = "\n".join(lines)
    print(f"  [INTERNAL_LAW] chain_law_system HIT: {system_key} ({total_found} items, {len(result)} chars)")
    return f"[내부DB] {result}"


def chain_full_research_internal(query: str) -> Optional[str]:
    """
    하이브리드 종합 리서치.
    - 법령/행정규칙: 내부 DB (0ms)
    - 판례/해석례: 외부 MCP (필요 시)
    
    Returns:
        법령 부분 결과 (내부). 판례/해석례는 호출자가 별도로 외부 MCP 호출.
    """
    _load_law_db()
    if not _law_db_cache:
        return None
    
    # 법령 체계 분석 (내부)
    law_result = chain_law_system_internal(query)
    
    # 추가: 쿼리에서 직접 언급된 조문도 포함
    _, article_no = _extract_law_and_article(query)
    direct_result = None
    if article_no:
        direct_result = search_internal_law(query)
    
    parts = []
    if law_result:
        parts.append(law_result)
    if direct_result and direct_result not in (law_result or ""):
        parts.append(direct_result)
    
    if not parts:
        return None
    
    return "\n\n".join(parts)
