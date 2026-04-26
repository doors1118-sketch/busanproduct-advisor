"""
혁신제품·기술개발제품 구조화 검색 (innovation_search)
- search_innovation_products: product_name 키워드 1순위 + ChromaDB 시맨틱 보조
- search_tech_development_products: tech_products.json 키워드 검색
- 사업자등록번호 정규화·조인 (내부 매칭 전용, 외부 미노출)
"""
import os
import re
import json
from datetime import datetime
from typing import Optional

# ─────────────────────────────────────────────
# 기술개발제품 13종 분류 매핑
# ─────────────────────────────────────────────
TECH_CERT_TYPES_13 = [
    "성능인증", "우수조달물품지정", "우수조달물품", "NEP", "GS인증", "GS", "NET",
    "우수조달 공동상표", "물산업우수제품 등 지정", "물산업 우수제품 등 지정",
    "혁신제품", "녹색기술제품", "산업융합 신제품 적합성 인증", "산업융합품목",
    "수요처 지정형 기술개발제품", "재난안전제품인증",
    "구매조건부신기술개발", "혁신시제품", "우수연구개발혁신제품",
]

# 혁신제품 계열 cert_type → innovation_product에도 포함
INNOVATION_CERT_TYPES = {"혁신제품", "우수연구개발혁신제품", "혁신시제품", "기타혁신제품"}

# ─────────────────────────────────────────────
# 유틸리티
# ─────────────────────────────────────────────
def normalize_business_no(raw: str) -> str:
    """사업자등록번호 정규화: 하이픈 제거, 10자리 문자열"""
    bno = re.sub(r"[^0-9]", "", str(raw).strip())
    if len(bno) == 9:
        bno = "0" + bno
    return bno if len(bno) == 10 else ""


def _check_cert_validity(expire_date: str) -> str:
    """인증 만료 여부 → '유효' / '만료' / '확인 필요'"""
    if not expire_date or expire_date in ("", "None", "nan"):
        return "확인 필요"
    clean = re.sub(r"[^0-9]", "", str(expire_date))[:8]
    if not clean or len(clean) < 8:
        return "확인 필요"
    try:
        today = datetime.now().strftime("%Y%m%d")
        return "유효" if clean >= today else "만료"
    except Exception:
        return "확인 필요"


def _detect_query_intent(query: str) -> str:
    """쿼리 의도 판별: product / company / cert_no"""
    company_patterns = [r"\(주\)", r"주식회사", r"㈜", r"\bco\b", r"\binc\b", r"\bltd\b"]
    for p in company_patterns:
        if re.search(p, query, re.IGNORECASE):
            return "company"
    cert_patterns = [r"\d{4}-\d+", r"제\d+호", r"[A-Z]{2,}-\d+"]
    for p in cert_patterns:
        if re.search(p, query):
            return "cert_no"
    return "product"


def _keyword_match_score(text: str, query_keywords: list) -> tuple:
    """키워드 매칭 점수 (0.0~1.0) + exact_match 여부"""
    if not text or not query_keywords:
        return 0.0, False
    text_lower = text.lower()
    matched = sum(1 for kw in query_keywords if kw in text_lower)
    score = matched / len(query_keywords) if query_keywords else 0.0
    exact = any(kw == text_lower for kw in query_keywords)
    return score, exact


def _extract_search_keywords(query: str) -> list:
    """쿼리에서 검색 키워드 추출 (불용어 제거)"""
    stopwords = {"혁신제품", "혁신시제품", "혁신", "부산", "업체", "찾아줘", "추천해줘",
                 "있어", "있나요", "관련", "등록된", "부산업체", "제품", "인증",
                 "수의계약", "구매", "검토", "해줘", "알려줘", "조회"}
    tokens = re.split(r"[\s,?!·]+", query.lower().strip())
    return [t for t in tokens if t and t not in stopwords and len(t) >= 2]


def classify_innovation_product_type(raw: str) -> str:
    """혁신제품 구분 정규화"""
    mapping = {
        "유형1": "혁신제품(유형1)", "유형2": "혁신제품(유형2)",
        "혁신시제품": "혁신시제품", "우수연구개발혁신제품": "우수연구개발혁신제품",
    }
    for k, v in mapping.items():
        if k in str(raw):
            return v
    return str(raw) if raw else "확인 필요"


def classify_priority_purchase_product_type(raw: str) -> str:
    """기술개발제품 13종 인증구분 정규화"""
    norm_map = {
        "GS": "GS인증", "NET": "NET", "NEP": "NEP",
        "우수조달물품": "우수조달물품지정", "성능인증": "성능인증",
        "녹색기술제품": "녹색기술제품", "재난안전제품인증": "재난안전제품인증",
        "물산업우수제품 등 지정": "물산업 우수제품 등 지정",
        "물산업 우수제품 등 지정": "물산업 우수제품 등 지정",
        "구매조건부신기술개발": "구매조건부신기술개발",
        "혁신시제품": "혁신시제품", "우수연구개발혁신제품": "우수연구개발혁신제품",
        "혁신제품": "혁신제품",
    }
    r = str(raw).strip()
    return norm_map.get(r, r)


# ─────────────────────────────────────────────
# 혁신제품 검색 (ChromaDB)
# ─────────────────────────────────────────────
_innovation_meta_cache = None

def _load_innovation_metadata() -> list:
    """ChromaDB innovation 컬렉션에서 전체 메타데이터 로드 (키워드 인덱스용)"""
    global _innovation_meta_cache
    if _innovation_meta_cache is not None:
        return _innovation_meta_cache

    try:
        import chromadb
        chroma_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".chroma")
        client = chromadb.PersistentClient(path=chroma_dir)
        collection = client.get_collection(name="innovation")
        # 전체 메타데이터 가져오기
        result = collection.get(include=["metadatas", "documents"])
        items = []
        for i, meta in enumerate(result["metadatas"]):
            doc = result["documents"][i] if result["documents"] else ""
            items.append({
                "id": result["ids"][i],
                "meta": meta,
                "document": doc,
            })
        _innovation_meta_cache = items
        return items
    except Exception as e:
        print(f"  [innovation_search] ChromaDB load failed: {e}")
        _innovation_meta_cache = []
        return []


def search_innovation_products(query: str, n_results: int = 10) -> dict:
    """
    혁신제품 구조화 검색.
    검색 우선순위:
    1. product_name exact/partial match
    2. certification_no exact match
    3. company_name exact/partial match
    4. ChromaDB semantic search (보조)

    Returns: {
        "query": str, "query_intent": str,
        "product_sample_rows": [...], "low_confidence_results": [...],
        "innovation_product_count": int, ...
    }
    """
    intent = _detect_query_intent(query)
    keywords = _extract_search_keywords(query)
    all_items = _load_innovation_metadata()

    if not all_items:
        return _empty_innovation_result(query, intent, "ChromaDB 컬렉션 로드 실패")

    # ── 1단계: 키워드 인덱스 스코어링 ──
    scored = []
    for item in all_items:
        meta = item["meta"]
        pname = str(meta.get("product_name", ""))
        cname = str(meta.get("company", ""))
        cert_no = str(meta.get("cert_no", ""))
        model = str(meta.get("model", ""))

        # product_name 매칭
        pn_score, pn_exact = _keyword_match_score(pname, keywords)
        # company_name 매칭
        cn_score, cn_exact = _keyword_match_score(cname, keywords)
        # cert_no exact
        cert_exact = any(kw in cert_no.lower() for kw in keywords) if keywords else False
        # model 매칭
        model_score, _ = _keyword_match_score(model, keywords)

        # 매칭 근거 결정
        match_basis = "semantic_similarity"
        if pn_exact or pn_score >= 0.5:
            match_basis = "product_name"
        elif cert_exact:
            match_basis = "certification_no"
        elif cn_exact or cn_score >= 0.5:
            match_basis = "company_name"

        # 종합 점수 (intent에 따라 가중치 조정)
        if intent == "product":
            total = pn_score * 3.0 + model_score * 1.0 + cn_score * 0.5 + (1.0 if cert_exact else 0.0)
        elif intent == "company":
            total = cn_score * 3.0 + pn_score * 1.0 + model_score * 0.5 + (1.0 if cert_exact else 0.0)
        else:  # cert_no
            total = (3.0 if cert_exact else 0.0) + pn_score * 0.5 + cn_score * 0.5

        if total > 0:
            scored.append({
                "item": item,
                "total_score": total,
                "product_name_match_score": round(pn_score, 3),
                "exact_match": pn_exact or cn_exact or cert_exact,
                "match_basis": match_basis,
            })

    # ── 2단계: ChromaDB 시맨틱 검색 보조 ──
    semantic_ids = set()
    semantic_scores = {}
    try:
        import chromadb
        from embedding import get_query_embedding_fn
        chroma_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".chroma")
        client = chromadb.PersistentClient(path=chroma_dir)
        embedding_fn = get_query_embedding_fn()
        collection = client.get_collection(name="innovation", embedding_function=embedding_fn)
        sem_results = collection.query(query_texts=[query], n_results=min(n_results * 3, 50))
        if sem_results["ids"][0]:
            for idx, sid in enumerate(sem_results["ids"][0]):
                semantic_ids.add(sid)
                dist = sem_results["distances"][0][idx] if sem_results.get("distances") else 1.0
                semantic_scores[sid] = round(max(0, 1.0 - dist), 3)
    except Exception:
        pass

    # 시맨틱 결과를 키워드 매칭 결과에 보조 가산
    scored_ids = {s["item"]["id"] for s in scored}
    for item in all_items:
        if item["id"] in semantic_ids and item["id"] not in scored_ids:
            sem_s = semantic_scores.get(item["id"], 0.0)
            if sem_s > 0.3:
                scored.append({
                    "item": item,
                    "total_score": sem_s * 0.5,
                    "product_name_match_score": 0.0,
                    "exact_match": False,
                    "match_basis": "semantic_similarity",
                })

    # 기존 키워드 매칭에 시맨틱 점수 보조 가산
    for s in scored:
        sid = s["item"]["id"]
        sem_s = semantic_scores.get(sid, 0.0)
        s["semantic_score"] = sem_s
        s["total_score"] += sem_s * 0.3

    # ── 3단계: 정렬 + 상위 n_results ──
    scored.sort(key=lambda x: -x["total_score"])
    top = scored[:n_results]

    # ── 4단계: 구조화 결과 생성 ──
    product_rows = []
    low_confidence = []
    valid_count = 0
    expired_count = 0
    unknown_count = 0

    for s in top:
        meta = s["item"]["meta"]
        pname = str(meta.get("product_name", ""))
        validity = _check_cert_validity(str(meta.get("cert_no", "")))
        # cert_no 기반 유효기간은 연도 추출로 판별
        cert_no = str(meta.get("cert_no", ""))
        # 혁신제품 인증번호 기반 유효기간 판별 → 운영용 "확인 필요"로 통일
        # (인증번호만으로는 정확한 만료일 판별 불가)
        validity = "확인 필요"

        innov_type = classify_innovation_product_type(str(meta.get("innovation_type", "")))

        row = {
            "candidate_types": ["innovation_product"],
            "primary_candidate_type": "innovation_product",
            "purchase_routes": ["혁신제품 수의계약 검토", "혁신장터 구매", "조달청 시범구매", "우선구매 검토"],
            "source_label": "혁신제품·혁신시제품 수의계약 검토 후보",
            "company_name": str(meta.get("company", "")),
            "product_name": pname,
            "location": str(meta.get("location", "")),
            "innovation_type": innov_type,
            "innovation_product_status": innov_type,
            "certification_type": str(meta.get("innovation_type", "")),
            "certification_no": cert_no,
            "certification_date": "",
            "certification_valid_until": validity,
            "patent_info_available": False,
            "innovation_market_registered": None,  # 미확인 → required_checks에 등록 확인 포함
            "shopping_mall_registered": None,  # 미확인 → required_checks에 등록 확인 포함
            "business_status": "확인 필요",
            "legal_eligibility_status": "확인 필요",
            "display_status": "후보",
            "required_checks": [
                "지정 유효기간 확인",
                "혁신장터 등록 여부 확인 (현재 미확인)",
                "종합쇼핑몰 등록 여부 확인 (현재 미확인)",
                "조달청 계약 여부 확인",
                "수요기관 적용 법령 확인",
                "수의계약 가능 근거 확인",
                "제품·규격 일치 여부 확인",
            ],
            "contract_possible_auto_promoted": False,
            "match_basis": s["match_basis"],
            "product_name_match_score": s["product_name_match_score"],
            "semantic_score": s.get("semantic_score", 0.0),
            "exact_match": s["exact_match"],
        }

        if validity == "확인 필요":
            unknown_count += 1
        elif validity == "유효":
            valid_count += 1
        else:
            expired_count += 1

        if not pname or pname in ("", "nan", "None", "설명 확인 필요"):
            low_confidence.append(row)
        else:
            product_rows.append(row)

    pn_matched = sum(1 for r in product_rows if r["match_basis"] == "product_name")
    cn_matched = sum(1 for r in product_rows if r["match_basis"] == "company_name")

    return {
        "query": query,
        "query_intent": intent,
        "product_name_query": " ".join(keywords),
        "data_source_status": "connected_local_search",
        "runtime_tool_integration": "pending",
        "innovation_product_count": len(product_rows),
        "product_name_matched_count": pn_matched,
        "company_name_matched_count": cn_matched,
        "low_confidence_count": len(low_confidence),
        "valid_cert_count": valid_count,
        "expired_cert_count": expired_count,
        "unknown_cert_count": unknown_count,
        "product_sample_rows": product_rows,
        "low_confidence_results": low_confidence,
        "sensitive_fields_removed": True,
        "sensitive_fields_detected": [],
        "contract_possible_auto_promoted": False,
        "legal_eligibility_status": "확인 필요",
    }


def _empty_innovation_result(query, intent, reason):
    return {
        "query": query, "query_intent": intent, "product_name_query": "",
        "data_source_status": "connected_local_search",
        "runtime_tool_integration": "pending",
        "innovation_product_count": 0, "product_name_matched_count": 0,
        "company_name_matched_count": 0, "low_confidence_count": 0,
        "valid_cert_count": 0, "expired_cert_count": 0, "unknown_cert_count": 0,
        "product_sample_rows": [], "low_confidence_results": [],
        "sensitive_fields_removed": True, "sensitive_fields_detected": [],
        "contract_possible_auto_promoted": False,
        "legal_eligibility_status": "확인 필요",
        "failure_reason": reason,
    }


# ─────────────────────────────────────────────
# 기술개발제품 13종 검색 (tech_products.json)
# ─────────────────────────────────────────────
_tech_db_cache = None

def _load_tech_db() -> dict:
    global _tech_db_cache
    if _tech_db_cache is not None:
        return _tech_db_cache
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tech_products.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            _tech_db_cache = json.load(f)
    else:
        _tech_db_cache = {"products": []}
    return _tech_db_cache


def search_tech_development_products(query: str, max_results: int = 10) -> dict:
    """
    기술개발제품 13종 키워드 검색 → 구조화 dict.
    사업자등록번호·대표자명은 내부 매칭 전용, 외부 미노출.
    """
    db = _load_tech_db()
    products = db.get("products", [])
    keywords = _extract_search_keywords(query)

    if not products:
        return _empty_tech_result(query, "tech_products.json 로드 실패 또는 비어있음")

    scored = []
    for p in products:
        pname = str(p.get("product_name", ""))
        cname = str(p.get("company", ""))
        cert_type = str(p.get("cert_type", ""))
        cert_no = str(p.get("cert_no", ""))

        pn_score, pn_exact = _keyword_match_score(pname, keywords)
        cn_score, cn_exact = _keyword_match_score(cname, keywords)
        ct_score, _ = _keyword_match_score(cert_type, keywords)

        total = pn_score * 3.0 + cn_score * 1.0 + ct_score * 1.5
        if total > 0:
            scored.append({"product": p, "total": total, "pn_score": pn_score})

    scored.sort(key=lambda x: -x["total"])
    top = scored[:max_results]

    rows = []
    valid_count = 0
    expired_count = 0
    matched_biz = 0

    for s in top:
        p = s["product"]
        cert_type_norm = classify_priority_purchase_product_type(p.get("cert_type", ""))
        validity = _check_cert_validity(p.get("expire_date", ""))

        c_types = ["priority_purchase_product"]
        if cert_type_norm in ("혁신제품", "혁신시제품", "우수연구개발혁신제품"):
            c_types.append("innovation_product")

        if validity == "유효":
            valid_count += 1
        elif validity == "만료":
            expired_count += 1

        bno = normalize_business_no(p.get("biz_no", ""))
        if bno:
            matched_biz += 1

        row = {
            "candidate_types": c_types,
            "primary_candidate_type": "priority_purchase_product",
            "purchase_routes": [
                "기술개발제품 우선구매 검토", "해당 인증제품 구매 검토",
                "수의계약 가능성 검토", "입찰·수의계약 검토",
            ],
            "source_label": "기술개발제품 13종 인증 보유 부산업체 우선구매 검토 후보",
            "company_name": str(p.get("company", "")),
            "product_name": str(p.get("product_name", "")),
            "certification_type": cert_type_norm,
            "certification_no": str(p.get("cert_no", "")),
            "certification_date": str(p.get("cert_date", "")),
            "certification_valid_until": validity,
            "location": "부산",
            "business_status": "확인 필요",
            "legal_eligibility_status": "확인 필요",
            "display_status": "후보",
            "required_checks": [
                "인증 유효기간 확인", "인증제품명과 구매 품목 일치 여부 확인",
                "부산 조달업체 매칭 여부 확인", "조달등록 또는 종합쇼핑몰 등록 여부 확인",
                "수요기관 적용 법령 확인", "금액 및 계약방식 확인",
            ],
            "contract_possible_auto_promoted": False,
        }
        rows.append(row)

    return {
        "query": query,
        "data_source_status": "connected_local_search",
        "runtime_tool_integration": "pending",
        "priority_purchase_count": len(rows),
        "matched_business_no_count": matched_biz,
        "unmatched_tech_product_count": len(products) - matched_biz if matched_biz else 0,
        "total_source_product_count": len(products),
        "valid_cert_count": valid_count,
        "expired_cert_count": expired_count,
        "product_sample_rows": rows,
        "sensitive_fields_removed": True,
        "sensitive_fields_detected": [],
        "contract_possible_auto_promoted": False,
        "legal_eligibility_status": "확인 필요",
    }


def _empty_tech_result(query, reason):
    return {
        "query": query, "data_source_status": "connected_local_search",
        "runtime_tool_integration": "pending",
        "priority_purchase_count": 0, "matched_business_no_count": 0,
        "unmatched_tech_product_count": 0, "valid_cert_count": 0,
        "expired_cert_count": 0, "product_sample_rows": [],
        "sensitive_fields_removed": True, "sensitive_fields_detected": [],
        "contract_possible_auto_promoted": False, "legal_eligibility_status": "확인 필요",
        "failure_reason": reason,
    }


# ─────────────────────────────────────────────
# 사업자등록번호 기반 부산 업체 매칭
# ─────────────────────────────────────────────
def match_busan_procurement_companies_by_business_no(products: list) -> dict:
    """tech_products 리스트에서 부산 조달업체 DB와 사업자번호 매칭 통계"""
    policy_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "policy_companies.json")
    busan_biz = set()
    if os.path.exists(policy_path):
        with open(policy_path, "r", encoding="utf-8") as f:
            busan_biz = set(json.load(f).keys())

    matched = 0
    unmatched = 0
    for p in products:
        bno = normalize_business_no(p.get("biz_no", ""))
        if bno and bno in busan_biz:
            matched += 1
        else:
            unmatched += 1

    return {"matched": matched, "unmatched": unmatched, "total": len(products)}
