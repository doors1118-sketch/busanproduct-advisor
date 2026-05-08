"""
내부 법령 DB 조회 모듈 (Internal Law Lookup)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MCP preflight 및 LLM 도구 호출 시 외부 법제처 API 대신
내부 DB를 우선 조회하고, 내부 DB에 없을 때만 외부 MCP를 보완적으로 호출.

내부 데이터 소스:
  1. law_articles_db.json — 법률·시행령·시행규칙 조문
  2. admin_rules_db.json — 예규·고시·훈령·집행기준 조문/첨부 원문
  3. key_articles.json — 레거시 핵심 조문 (7종, 보완용)
  ※ ordinances_db.json — 조례/자치법규는 참고 보관용이며 4단계 체인 기본 조회에서 제외

조회 흐름:
  law_articles_db.json + admin_rules_db.json 통합 인덱스
  → key_articles.json (보완) → 외부 MCP (fallback)
"""
import os
import re
import json
import threading
from typing import Optional, List, Tuple

_ROOT = os.path.dirname(os.path.abspath(__file__))
_LAW_DB_PATH = os.path.join(_ROOT, "data", "law_articles_db.json")
_ADMIN_RULES_DB_PATH = os.path.join(_ROOT, "data", "admin_rules_db.json")
_LAW_ANNEX_DB_PATH = os.path.join(_ROOT, "data", "law_annexes_db.json")
_ADMIN_RULE_ANNEX_DB_PATH = os.path.join(_ROOT, "data", "admin_rule_annexes_db.json")
_KEY_ARTICLES_PATH = os.path.join(_ROOT, "data", "key_articles.json")

# ─────────────────────────────────────────────
# DB 로딩 (1회 캐싱)
# ─────────────────────────────────────────────
_law_db_cache: dict = None
_key_articles_cache: dict = None
# 빠른 조회용 인덱스: "지방계약법 시행령 제25조" → 조문 텍스트
_lookup_index: dict = None
# MST → short_name 역매핑 (get_law_text 내부 DB 지원용)
_mst_to_short: dict = None
_annex_db_cache: dict = None
_load_lock = threading.RLock()
_annex_load_lock = threading.RLock()


def _load_law_db() -> dict:
    global _law_db_cache, _lookup_index, _mst_to_short
    if _law_db_cache is not None:
        return _law_db_cache
    with _load_lock:
        if _law_db_cache is not None:
            return _law_db_cache

        loaded_sources = []
        try:
            merged_db = {}
            for source_path, source_label in (
                (_LAW_DB_PATH, "law_articles_db.json"),
                (_ADMIN_RULES_DB_PATH, "admin_rules_db.json"),
            ):
                if not os.path.exists(source_path):
                    continue
                with open(source_path, "r", encoding="utf-8") as f:
                    source_db = json.load(f)
                if isinstance(source_db, dict):
                    merged_db.update(source_db)
                    loaded_sources.append(f"{source_label}:{len(source_db)}")

            lookup_index = {}
            mst_to_short = {}
            total_articles = 0
            for short_name, law_data in merged_db.items():
                # MST 역매핑
                mst = law_data.get("mst", "")
                if mst:
                    mst_to_short[str(mst)] = short_name
                articles = law_data.get("articles", {})
                for article_no, article_data in articles.items():
                    # "지방계약법 시행령 제25조" → 조문 텍스트
                    lookup_key = f"{short_name} {article_no}"
                    lookup_index[lookup_key] = article_data.get("text", "")
                    total_articles += 1

            _law_db_cache = merged_db
            _lookup_index = lookup_index
            _mst_to_short = mst_to_short
            source_note = ", ".join(loaded_sources) if loaded_sources else "no source files"
            print(f"  [INTERNAL_LAW] 내부 법령 통합 DB 로드: {len(_law_db_cache)}개 소스, {total_articles}개 조문 ({source_note})")
        except Exception as e:
            print(f"  [INTERNAL_LAW] 내부 법령 통합 DB 로드 실패: {e}")
            _law_db_cache = {}
            _lookup_index = {}
            _mst_to_short = {}
    return _law_db_cache


def _load_annex_db() -> dict:
    global _annex_db_cache
    if _annex_db_cache is not None:
        return _annex_db_cache
    with _annex_load_lock:
        if _annex_db_cache is not None:
            return _annex_db_cache
        merged = {}
        loaded = []
        for path, label in (
            (_LAW_ANNEX_DB_PATH, "law_annexes_db.json"),
            (_ADMIN_RULE_ANNEX_DB_PATH, "admin_rule_annexes_db.json"),
        ):
            if not os.path.exists(path):
                continue
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    merged.update(data)
                    loaded.append(f"{label}:{len(data)}")
            except Exception as e:
                print(f"  [INTERNAL_LAW] annex DB 로드 실패({label}): {e}")
        _annex_db_cache = merged
        if loaded:
            print(f"  [INTERNAL_LAW] 내부 별표 DB 로드: {len(merged)}개 소스 ({', '.join(loaded)})")
        return _annex_db_cache


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
    "중소기업제품 구매촉진 및 판로지원법 시행령": "중소기업제품 구매촉진법 시행령",
    "중소기업제품 구매촉진 및 판로지원법": "중소기업제품 구매촉진 및 판로지원법",
    "중소기업제품 구매촉진법 시행령": "중소기업제품 구매촉진법 시행령",
    "중소기업제품 구매촉진법": "중소기업제품 구매촉진 및 판로지원법",
    "중소기업구매촉진법 시행규칙": "중소기업구매촉진법 시행규칙",
    "중소기업구매촉진법 시행령": "중소기업제품 구매촉진법 시행령",
    "중소기업구매촉진법": "중소기업제품 구매촉진 및 판로지원법",
    "조달사업법 시행규칙": "조달사업법 시행규칙",
    "조달사업법 시행령": "조달사업법 시행령",
    "조달사업법": "조달사업법",
    "공기업ㆍ준정부기관 계약사무규칙": "공기업ㆍ준정부기관 계약사무규칙",
    "공기업및준정부기관 계약사무규칙": "공기업ㆍ준정부기관 계약사무규칙",
    "공기업 및 준정부기관 계약사무규칙": "공기업ㆍ준정부기관 계약사무규칙",
    "공기업계약사무규칙": "공기업ㆍ준정부기관 계약사무규칙",
    "계약사무규칙": "공기업ㆍ준정부기관 계약사무규칙",
    "전기공사업법 시행규칙": "전기공사업법 시행규칙",
    "전기공사업법 시행령": "전기공사업법 시행령",
    "전기공사업법": "전기공사업법",
    "정보통신공사업법 시행규칙": "정보통신공사업법 시행규칙",
    "정보통신공사업법 시행령": "정보통신공사업법 시행령",
    "정보통신공사업법": "정보통신공사업법",
    "소프트웨어 진흥법 시행규칙": "소프트웨어 진흥법 시행규칙",
    "소프트웨어 진흥법 시행령": "소프트웨어 진흥법 시행령",
    "소프트웨어 진흥법": "소프트웨어 진흥법",
    "소프트웨어진흥법 시행규칙": "소프트웨어 진흥법 시행규칙",
    "소프트웨어진흥법 시행령": "소프트웨어 진흥법 시행령",
    "소프트웨어진흥법": "소프트웨어 진흥법",
    "건설산업기본법 시행규칙": "건설산업기본법 시행규칙",
    "건설산업기본법 시행령": "건설산업기본법 시행령",
    "건설산업기본법": "건설산업기본법",
    "건설기술 진흥법 시행규칙": "건설기술 진흥법 시행규칙",
    "건설기술 진흥법 시행령": "건설기술 진흥법 시행령",
    "건설기술 진흥법": "건설기술 진흥법",
    "건설기술진흥법 시행규칙": "건설기술 진흥법 시행규칙",
    "건설기술진흥법 시행령": "건설기술 진흥법 시행령",
    "건설기술진흥법": "건설기술 진흥법",
    "소방시설공사업법 시행규칙": "소방시설공사업법 시행규칙",
    "소방시설공사업법 시행령": "소방시설공사업법 시행령",
    "소방시설공사업법": "소방시설공사업법",
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
        if text and text.strip():
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
    if "조례" in query or "자치법규" in query:
        print("  [INTERNAL_LAW] admin_rule SKIP: ordinance query is excluded from 4-step chain")
        return None

    def _is_rule_like(short_name: str, law_data: dict) -> bool:
        source = law_data.get("source", "")
        source_type = law_data.get("source_type", "")
        return (
            "행정규칙" in source
            or source_type == "admin_rule"
            or any(token in short_name for token in (
                "예규", "규정", "요령", "기준", "유의서", "세칙", "내역"
            ))
        )
    
    # 행정규칙명 직접 매칭
    for short_name, law_data in _law_db_cache.items():
        if not _is_rule_like(short_name, law_data):
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
        if not _is_rule_like(short_name, law_data):
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


def _compact_name(value: str) -> str:
    return (value or "").replace(" ", "").replace("ㆍ", "").replace("·", "").lower()


def search_internal_annexes(law_name: str, annex_no: str = None) -> Optional[str]:
    """
    내부 DB에서 법령/행정규칙 별표·서식 정보를 우선 조회한다.

    law_annexes_db.json / admin_rule_annexes_db.json이 있으면 이를 우선 사용하고,
    아직 별표 DB가 없는 행정규칙은 기존 admin_rules_db의 첨부 메타데이터로 보완한다.
    """
    _load_law_db()
    annex_db = _load_annex_db()
    if not law_name:
        return None

    query_clean = _compact_name(law_name)

    def _match_source(db: dict) -> tuple[str, dict] | None:
        for short_name, law_data in sorted(db.items(), key=lambda item: len(_compact_name(item[0])), reverse=True):
            name_clean = _compact_name(short_name)
            full_clean = _compact_name(law_data.get("full_name", ""))
            short_clean = _compact_name(law_data.get("short_name", ""))
            if (
                query_clean in name_clean or name_clean in query_clean
                or (full_clean and (query_clean in full_clean or full_clean in query_clean))
                or (short_clean and (query_clean in short_clean or short_clean in query_clean))
            ):
                return short_name, law_data
        return None

    matched = _match_source(annex_db or {})
    if matched:
        short_name, law_data = matched
        annexes = law_data.get("annexes") or {}
        attachment_links = law_data.get("attachment_links") or []
        attachment_paths = law_data.get("attachment_paths") or []
        attachment_refs = law_data.get("attachment_references") or []

        filtered_annexes = []
        for key, annex in annexes.items():
            title = annex.get("title", "")
            text = annex.get("text", "")
            no = str(annex.get("annex_no", ""))
            if annex_no and annex_no not in no and annex_no not in title and annex_no not in text[:500]:
                continue
            filtered_annexes.append((key, annex))

        if filtered_annexes or attachment_links or attachment_paths or attachment_refs:
            lines = [
                f"[내부DB] {short_name} 별표/서식",
                f"자료유형: {law_data.get('source_type', '')}",
            ]
            effective_date = law_data.get("effective_date")
            if effective_date:
                lines.append(f"시행일자: {effective_date}")

            if filtered_annexes:
                lines.append("▶ 별표/서식 원문")
                limit = 8 if annex_no else 4
                text_limit = 5000 if annex_no else 2500
                for key, annex in filtered_annexes[:limit]:
                    title = annex.get("title") or annex.get("annex_no") or key
                    related = ", ".join(annex.get("related_articles") or [])
                    lines.append(f"[{title}]")
                    if related:
                        lines.append(f"관련 조문: {related}")
                    body = annex.get("text", "")
                    lines.append(body[:text_limit] if body else "(별표 제목만 수집됨)")
                    lines.append("")

            if attachment_links:
                lines.append("▶ 첨부파일 링크")
                for link in attachment_links[:5]:
                    name = link.get("name", "")
                    url = link.get("url", "")
                    lines.append(f"- {name}: {url}")

            if attachment_paths:
                lines.append("▶ 내부 보관 파일")
                for path in attachment_paths[:5]:
                    lines.append(f"- {path}")

            if attachment_refs:
                lines.append("▶ 첨부/별표 언급 조문")
                for ref in attachment_refs[:5]:
                    label = f"{short_name} {ref.get('article_no', '')}".strip()
                    lines.append(f"[{label}]")
                    lines.append((ref.get("text") or "")[:1500])
                    lines.append("")

            result = "\n".join(lines).strip()
            print(f"  [INTERNAL_LAW] annex DB HIT: {short_name} ({len(result)} chars)")
            return result

    if not _law_db_cache:
        return None

    # 별표 DB가 아직 없거나 비어 있는 행정규칙은 기존 통합 DB의 첨부 메타데이터로 보완한다.
    matched = None
    for short_name, law_data in sorted(_law_db_cache.items(), key=lambda item: len(_compact_name(item[0])), reverse=True):
        name_clean = _compact_name(short_name)
        full_clean = _compact_name(law_data.get("full_name", ""))
        if query_clean in name_clean or name_clean in query_clean or (full_clean and (query_clean in full_clean or full_clean in query_clean)):
            matched = (short_name, law_data)
            break

    if not matched:
        return None

    short_name, law_data = matched
    attachment_links = law_data.get("attachment_links") or []
    attachment_paths = law_data.get("attachment_paths") or []
    if not attachment_links and not attachment_paths:
        return None

    annex_terms = ["별표", "별지", "서식"]
    if annex_no:
        annex_terms.append(str(annex_no))

    lines = [
        f"[내부DB] {short_name} 별표/서식 첨부 정보",
        "※ 행정규칙 첨부파일과 첨부 원문 추출 텍스트 기준입니다.",
    ]
    effective_date = law_data.get("effective_date")
    if effective_date:
        lines.append(f"시행일자: {effective_date}")

    if attachment_links:
        lines.append("▶ 첨부파일 링크")
        for link in attachment_links[:5]:
            name = link.get("name", "")
            url = link.get("url", "")
            lines.append(f"- {name}: {url}")

    if attachment_paths:
        lines.append("▶ 내부 보관 파일")
        for path in attachment_paths[:5]:
            lines.append(f"- {path}")

    articles = law_data.get("articles", {})
    matched_articles = []
    for art_no, art_data in articles.items():
        text = art_data.get("text", "")
        if any(term in text for term in annex_terms):
            matched_articles.append((art_no, text))
        if len(matched_articles) >= 5:
            break

    if matched_articles:
        lines.append("▶ 별표/서식 언급 조문 및 추출 텍스트")
        for art_no, text in matched_articles:
            lines.append(f"[{short_name} {art_no}]")
            lines.append(text[:1500])
            lines.append("")

    result = "\n".join(lines).strip()
    print(f"  [INTERNAL_LAW] annex HIT: {short_name} ({len(result)} chars)")
    return result


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
        "법률": "중소기업제품 구매촉진 및 판로지원법",
        "시행령": "중소기업제품 구매촉진법 시행령",
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
        "시행규칙": "공기업ㆍ준정부기관 계약사무규칙",
        "행정규칙": [
            "기타공공기관 계약사무 운영규정",
        ],
    },
    "전기공사업법": {
        "법률": "전기공사업법",
        "시행령": "전기공사업법 시행령",
        "시행규칙": "전기공사업법 시행규칙",
        "행정규칙": [],
    },
    "정보통신공사업법": {
        "법률": "정보통신공사업법",
        "시행령": "정보통신공사업법 시행령",
        "시행규칙": "정보통신공사업법 시행규칙",
        "행정규칙": [],
    },
    "소프트웨어": {
        "법률": "소프트웨어 진흥법",
        "시행령": "소프트웨어 진흥법 시행령",
        "시행규칙": "소프트웨어 진흥법 시행규칙",
        "행정규칙": [
            "소프트웨어사업 계약 및 관리감독에 관한 지침",
            "소프트웨어 기술성 평가기준 지침",
        ],
    },
    "건설산업기본법": {
        "법률": "건설산업기본법",
        "시행령": "건설산업기본법 시행령",
        "시행규칙": "건설산업기본법 시행규칙",
        "행정규칙": [
            "건설공사 발주 세부기준",
        ],
    },
    "건설기술진흥법": {
        "법률": "건설기술 진흥법",
        "시행령": "건설기술 진흥법 시행령",
        "시행규칙": "건설기술 진흥법 시행규칙",
        "행정규칙": [
            "건설공사 발주 세부기준",
        ],
    },
    "소방시설공사업법": {
        "법률": "소방시설공사업법",
        "시행령": "소방시설공사업법 시행령",
        "시행규칙": "소방시설공사업법 시행규칙",
        "행정규칙": [],
    },
}


def _detect_law_system(query: str) -> str:
    """쿼리에서 법체계 계열 감지."""
    query_upper = query.upper()
    if "전기공사" in query:
        return "전기공사업법"
    if "정보통신공사" in query or "통신공사" in query:
        return "정보통신공사업법"
    if "소프트웨어" in query or "상용소프트웨어" in query or "SW" in query_upper:
        return "소프트웨어"
    if "건설기술" in query or "건설사업관리" in query or "건설감리" in query:
        return "건설기술진흥법"
    if "건설산업" in query or "건설업" in query or "건설공사" in query or "토목" in query or "건축공사" in query:
        return "건설산업기본법"
    if "소방시설" in query or "소방공사" in query:
        return "소방시설공사업법"
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


def _extract_keywords(text: str) -> List[str]:
    """텍스트에서 2글자 이상 키워드를 추출한다.
    조사/어미를 제거하고 핵심 키워드만 반환."""
    # 공백/조사 기준 분리
    particles = ['은', '는', '이', '가', '을', '를', '에', '의', '로', '으로',
                 '에서', '과', '와', '도', '만', '까지', '부터', '에게', '한테',
                 '라고', '라는', '에는', '으로서', '이란', '이라']
    words = re.split(r'[\s,;.?!()\[\]{}·ㆍ]+', text)
    keywords = []
    for w in words:
        # 조사 제거
        for p in sorted(particles, key=len, reverse=True):
            if w.endswith(p) and len(w) > len(p) + 1:
                w = w[:-len(p)]
                break
        if len(w) >= 2:
            keywords.append(w)
    return keywords


def _get_relevant_articles(law_short: str, query: str, max_articles: int = 5) -> list:
    """해당 법령에서 쿼리와 관련된 핵심 조문 추출.
    키워드 단위 매칭 + 전체 텍스트 검색으로 정밀도 향상."""
    db = _law_db_cache or {}
    law_data = db.get(law_short)
    if not law_data:
        return []
    
    articles = law_data.get("articles", {})
    if not articles:
        return []
    
    query_keywords = _extract_keywords(query)
    scored = []
    for art_no, art_data in articles.items():
        text = art_data.get("text", "")
        title = art_data.get("title", "")
        cross_refs = art_data.get("cross_refs", [])  # DB에 저장된 위임 참조
        search_target = title + " " + text  # 전체 텍스트 검색
        # 키워드 단위 매칭: 각 키워드가 조문에 포함되면 가중치 부여
        score = 0
        for kw in query_keywords:
            if kw in search_target:
                score += len(kw)  # 긴 키워드일수록 높은 점수
        scored.append((score, art_no, title, text, cross_refs))
    
    scored.sort(reverse=True)
    return [(no, title, text, crefs) for _, no, title, text, crefs in scored[:max_articles] if _ >= 4]


def _extract_cross_references(text: str) -> List[Tuple[str, str]]:
    """조문 텍스트에서 위임 참조(「법령명」 제X조)를 추출한다.
    
    예: '「국가계약법 시행규칙」 제24조제2항' → ('국가계약법 시행규칙', '제24조')
    
    Returns:
        [(법령 약칭, 조문번호), ...]
    """
    refs = []
    # 패턴: 「법령명」 제X조(의Y)
    pattern = r'「([^」]+)」[^제]{0,10}(제\d+조(?:의\d+)?)'
    for match in re.finditer(pattern, text):
        law_full_name = match.group(1).strip()
        article_no = match.group(2)
        # 법령 풀네임을 약칭으로 변환
        short = None
        for pattern_key in sorted(_SHORT_NAME_MAP.keys(), key=len, reverse=True):
            if pattern_key in law_full_name:
                short = _SHORT_NAME_MAP[pattern_key]
                break
        # SHORT_NAME_MAP에 없으면 풀네임에서 직접 추출 시도
        if not short:
            for db_short in (_law_db_cache or {}).keys():
                if db_short in law_full_name or law_full_name in db_short:
                    short = db_short
                    break
        if short:
            refs.append((short, article_no))
    return refs


def chain_law_system_internal(query: str) -> Optional[str]:
    """
    내부 DB 전용 — 법률→시행령→시행규칙→행정규칙 4단 체계 분석.
    + 위임 참조 자동 추적 (depth=1)
    
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
    collected_refs = set()  # 이미 포함된 조문 추적 (중복 방지)
    pending_cross_refs = []  # 위임 참조 대기열
    
    # 4단계 순회
    for tier_name in ["법률", "시행령", "시행규칙"]:
        law_short = system.get(tier_name)
        if not law_short:
            continue
        
        relevant = _get_relevant_articles(law_short, query, max_articles=5)
        if relevant:
            lines.append(f"▶ {tier_name}: {law_short}")
            for art_no, title, text, cross_refs in relevant:
                title_str = f" ({title})" if title else ""
                lines.append(f"  {art_no}{title_str}")
                lines.append(f"  {text[:1200]}")
                lines.append("")
                total_found += 1
                collected_refs.add(f"{law_short} {art_no}")
                # 위임 참조 수집: DB의 cross_refs 필드 우선, 없으면 텍스트 추출
                if cross_refs:
                    for cr in cross_refs:
                        ref_key = f"{cr['law']} {cr['article']}"
                        if ref_key not in collected_refs:
                            pending_cross_refs.append((cr['law'], cr['article']))
                else:
                    text_refs = _extract_cross_references(text)
                    for ref_law, ref_art in text_refs:
                        ref_key = f"{ref_law} {ref_art}"
                        if ref_key not in collected_refs:
                            pending_cross_refs.append((ref_law, ref_art))
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
                # 행정규칙도 키워드 기반으로 관련 조문 검색
                rule_articles = _get_relevant_articles(rule_name, query, max_articles=3)
                if rule_articles:
                    lines.append(f"  ● {rule_name}")
                    for art_no, title, text, cross_refs in rule_articles:
                        title_str = f" ({title})" if title else ""
                        lines.append(f"    {art_no}{title_str}")
                        lines.append(f"    {text[:1000]}")
                        lines.append("")
                        total_found += 1
                        collected_refs.add(f"{rule_name} {art_no}")
                        # 행정규칙 조문에서도 위임 참조 수집
                        if cross_refs:
                            for cr in cross_refs:
                                ref_key = f"{cr['law']} {cr['article']}"
                                if ref_key not in collected_refs:
                                    pending_cross_refs.append((cr['law'], cr['article']))
                        else:
                            text_refs = _extract_cross_references(text)
                            for ref_law, ref_art in text_refs:
                                ref_key = f"{ref_law} {ref_art}"
                                if ref_key not in collected_refs:
                                    pending_cross_refs.append((ref_law, ref_art))
                else:
                    # 키워드 매칭 실패 시 첫 조문이라도 보여줌
                    articles = rule_data.get("articles", {})
                    first_text = ""
                    for art_data in list(articles.values())[:1]:
                        first_text = art_data.get("text", "")[:500]
                    lines.append(f"  ● {rule_name}")
                    if first_text:
                        lines.append(f"    {first_text}")
                    lines.append("")
                    total_found += 1
    
    # ── 위임 참조 자동 추적 (depth=1) ──
    if pending_cross_refs:
        unique_refs = []
        seen = set()
        for ref_law, ref_art in pending_cross_refs:
            key = f"{ref_law} {ref_art}"
            if key not in collected_refs and key not in seen:
                unique_refs.append((ref_law, ref_art))
                seen.add(key)
        
        if unique_refs:
            lines.append("")
            lines.append("▶ 위임 참조 조문 (자동 추적):")
            for ref_law, ref_art in unique_refs[:5]:  # 최대 5개
                lookup_key = f"{ref_law} {ref_art}"
                ref_text = (_lookup_index or {}).get(lookup_key, "")
                if ref_text:
                    lines.append(f"  ● {lookup_key}")
                    lines.append(f"    {ref_text[:1000]}")
                    lines.append("")
                    total_found += 1
                    print(f"  [INTERNAL_LAW] 위임 참조 추적: {lookup_key} ({len(ref_text)} chars)")
    
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
