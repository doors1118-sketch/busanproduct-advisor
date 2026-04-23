"""
핵심 법령 원문 — MCP 경유 법제처 API에서 수집 -> ChromaDB 적재

대상: 국가계약법, 지방계약법, 중소기업구매촉진법, 조달사업법,
      공기업계약사무규칙 및 각 시행령/시행규칙

※ 법제처 API는 IP 등록 필요 → NCP 서버(MCP) 경유로 수집

사용법:
    python ingest_laws.py          # 전체 적재
    python ingest_laws.py --update # 개정된 법령만 재적재
    python ingest_laws.py --test   # 1건 테스트
"""
import os
import re
import pickle
import time
import chromadb
from embedding import get_passage_embedding_fn, get_query_embedding_fn
from dotenv import load_dotenv

# 프로젝트 루트 기준 .env 로드
_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(_root), ".env"))

# MCP 클라이언트 (NCP 서버 경유)
import mcp_client as mcp

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
CHROMA_DIR = os.path.join(_root, ".chroma")
COLLECTION_NAME = "laws"
BM25_INDEX_PATH = os.path.join(_root, ".chroma", "bm25_laws_index.pkl")

embedding_fn_passage = get_passage_embedding_fn()
embedding_fn_query = get_query_embedding_fn()

# ─────────────────────────────────────────────
# 적재 대상 법령 목록 (MST + 약칭)
# ─────────────────────────────────────────────
LAW_LIST = [
    # L1: 핵심 계약법
    {"mst": "253973", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률", "short": "지방계약법", "tier": "L1"},
    {"mst": "281055", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령", "short": "지방계약법 시행령", "tier": "L1"},
    {"mst": "282729", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행규칙", "short": "지방계약법 시행규칙", "tier": "L1"},
    {"mst": "277151", "name": "국가를 당사자로 하는 계약에 관한 법률", "short": "국가계약법", "tier": "L1"},
    {"mst": "280803", "name": "국가를 당사자로 하는 계약에 관한 법률 시행령", "short": "국가계약법 시행령", "tier": "L1"},
    {"mst": "282607", "name": "국가를 당사자로 하는 계약에 관한 법률 시행규칙", "short": "국가계약법 시행규칙", "tier": "L1"},

    # L1: 중소기업 구매촉진
    {"mst": "277129", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률", "short": "중소기업구매촉진법", "tier": "L1"},
    {"mst": "281341", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령", "short": "중소기업구매촉진법 시행령", "tier": "L1"},
    {"mst": "253373", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행규칙", "short": "중소기업구매촉진법 시행규칙", "tier": "L1"},

    # L2: 조달사업법
    {"mst": "277155", "name": "조달사업에 관한 법률", "short": "조달사업법", "tier": "L2"},
    {"mst": "280891", "name": "조달사업에 관한 법률 시행령", "short": "조달사업법 시행령", "tier": "L2"},
    {"mst": "282675", "name": "조달사업에 관한 법률 시행규칙", "short": "조달사업법 시행규칙", "tier": "L2"},

    # L2: 공기업 계약사무규칙
    {"mst": "285569", "name": "공기업ㆍ준정부기관 계약사무규칙", "short": "공기업계약사무규칙", "tier": "L2"},
]


# ─────────────────────────────────────────────
# MCP 경유 법령 수집
# ─────────────────────────────────────────────

def fetch_law_articles_via_mcp(mst: str) -> list[dict]:
    """
    MCP 경유로 법령 전체 조문 수집.
    
    1) get_law_text(mst) → 목차에서 조번호 리스트 추출
    2) get_law_text(mst, jo=제N조) → 개별 조문 수집
    """
    # 1단계: 목차 가져오기
    try:
        toc_text = mcp.get_law_text(mst=mst)
    except Exception as e:
        print(f"  [ERROR] MCP get_law_text({mst}): {e}")
        return []

    if not toc_text or len(toc_text) < 10:
        return []

    # 목차에서 조번호 추출 (제1조, 제2조, 제13조의2 등)
    article_numbers = re.findall(r'(제\d+조(?:의\d+)?)', toc_text)
    # 중복 제거 (순서 유지)
    seen = set()
    unique_articles = []
    for a in article_numbers:
        if a not in seen:
            seen.add(a)
            unique_articles.append(a)
    
    if not unique_articles:
        # 목차에서 조번호를 못 찾으면 전체 텍스트를 청크로
        return _chunk_raw_text(toc_text, mst)

    print(f"  -> {len(unique_articles)}개 조문 발견, 개별 수집 중...")

    # 2단계: 각 조문 수집
    articles = []
    for jo_no in unique_articles:
        try:
            jo_text = mcp.get_law_text(mst=mst, jo=jo_no)
            if jo_text and len(jo_text) > 10:
                # 조제목 추출 시도
                title_match = re.search(r'[（\(]([^)）]+)[）\)]', jo_text[:200])
                jo_title = title_match.group(1) if title_match else ""
                
                articles.append({
                    "조번호": jo_no,
                    "조제목": jo_title,
                    "조문전체": jo_text.strip(),
                })
        except Exception as e:
            print(f"    [SKIP] {jo_no}: {e}")
        
        time.sleep(0.3)  # API 부하 방지

    return articles


def _chunk_raw_text(text: str, mst: str) -> list[dict]:
    """정규식 매칭 실패 시: 전체 텍스트를 1000자 청크로 분할."""
    articles = []
    chunk_size = 1000
    for i in range(0, len(text), chunk_size):
        chunk = text[i:i+chunk_size]
        jo_match = re.search(r'제(\d+)조(?:의(\d+))?', chunk)
        jo_no = jo_match.group(0) if jo_match else f"chunk_{i//chunk_size}"
        articles.append({
            "조번호": jo_no,
            "조제목": "",
            "조문전체": chunk.strip(),
        })
    return articles


# ─────────────────────────────────────────────
# ChromaDB 적재
# ─────────────────────────────────────────────

def ingest_laws(update_mode: bool = False):
    """
    LAW_LIST의 모든 법령을 ChromaDB에 적재.
    
    update_mode=True: 시행일이 변경된 법령만 재적재.
    """
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if not update_mode:
        try:
            client.delete_collection(COLLECTION_NAME)
            print("  기존 laws 컬렉션 삭제")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn_passage,
        metadata={"description": "핵심 법령 원문 (조 단위)"},
    )

    # 기존 메타데이터 확인 (업데이트 모드)
    existing_dates = {}
    if update_mode:
        existing = collection.get(include=["metadatas"])
        for meta in existing.get("metadatas", []):
            law_name = meta.get("law_name", "")
            date = meta.get("enforcement_date", "")
            if law_name:
                existing_dates[law_name] = date

    total_added = 0
    total_skipped = 0

    for law in LAW_LIST:
        mst = law["mst"]
        name = law["name"]
        short = law["short"]
        tier = law["tier"]

        print(f"\n[{short}] MST={mst}")

        # 업데이트 모드: 이미 적재된 법령 스킵
        if update_mode and name in existing_dates:
            print(f"  -> SKIP (이미 적재됨)")
            total_skipped += 1
            continue

        # MCP 경유 조문 수집
        articles = fetch_law_articles_via_mcp(mst)
        if not articles:
            print(f"  -> WARNING: 조문 0건 (MCP 응답 없음)")
            continue

        enforcement_date = time.strftime("%Y%m%d")

        # ChromaDB 적재 준비
        ids = []
        documents = []
        metadatas = []

        for art in articles:
            doc_id = f"law_{mst}_{art['조번호']}"
            # 검색용 문서: [법령명] 제N조 (조제목) + 조문 전문
            doc_text = f"[{short}] {art['조번호']}"
            if art["조제목"]:
                doc_text += f" ({art['조제목']})"
            doc_text += f"\n{art['조문전체']}"

            ids.append(doc_id)
            documents.append(doc_text)
            metadatas.append({
                "law_name": name,
                "law_short": short,
                "article_no": art["조번호"],
                "article_title": art["조제목"],
                "tier": tier,
                "mst": mst,
                "enforcement_date": enforcement_date,
            })

        # 배치 적재
        batch_size = 500
        for i in range(0, len(ids), batch_size):
            end = min(i + batch_size, len(ids))
            collection.add(
                ids=ids[i:end],
                documents=documents[i:end],
                metadatas=metadatas[i:end],
            )

        print(f"  -> {len(ids)}개 조문 적재 완료 (시행일: {enforcement_date})")
        total_added += len(ids)
        time.sleep(0.5)  # API 부하 방지

    print(f"\n{'='*50}")
    print(f"적재 완료: {total_added}건 추가, {total_skipped}건 스킵")
    print(f"컬렉션 총 문서: {collection.count()}건")

    # ─── BM25 전역 인덱스 구축 ───
    _build_bm25_index(collection)


def _build_bm25_index(collection=None):
    """
    전체 법령 문서를 대상으로 BM25 인덱스를 구축하고 pickle 저장.
    적재 완료 후 자동 호출.
    """
    from rank_bm25 import BM25Okapi

    if collection is None:
        try:
            client = chromadb.PersistentClient(path=CHROMA_DIR)
            collection = client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_fn_passage,
            )
        except Exception:
            print("  [BM25] 컬렉션 없음 — 인덱스 구축 스킵")
            return

    # 전체 문서 로드
    all_data = collection.get(include=["documents", "metadatas"])
    all_docs = all_data["documents"]
    all_ids = all_data["ids"]
    all_metas = all_data["metadatas"]

    if not all_docs:
        print("  [BM25] 문서 0건 — 인덱스 구축 스킵")
        return

    print(f"\n[BM25] 전역 인덱스 구축 중... ({len(all_docs)}건 토큰화)")

    # 전체 문서 토큰화
    tokenized_corpus = [_legal_tokenize(doc) for doc in all_docs]

    # BM25 인덱스 생성
    bm25 = BM25Okapi(tokenized_corpus)

    # pickle 저장 (인덱스 + 문서 ID + 메타데이터)
    index_data = {
        "bm25": bm25,
        "ids": all_ids,
        "documents": all_docs,
        "metadatas": all_metas,
        "tokenized_corpus": tokenized_corpus,
    }

    os.makedirs(os.path.dirname(BM25_INDEX_PATH), exist_ok=True)
    with open(BM25_INDEX_PATH, "wb") as f:
        pickle.dump(index_data, f)

    print(f"  [BM25] index saved: {BM25_INDEX_PATH} ({os.path.getsize(BM25_INDEX_PATH) / 1024:.0f} KB)")


# ─────────────────────────────────────────────
# RAG 검색 함수 (gemini_engine에서 호출)
# ─────────────────────────────────────────────


# 기관 유형별 우선 검색 법령 매핑
AGENCY_LAW_MAP = {
    "지방자치단체(부산광역시)": [
        "지방계약법", "지방계약법 시행령", "지방계약법 시행규칙",
    ],
    "지방출자출연기관": [
        "지방계약법", "지방계약법 시행령", "지방계약법 시행규칙",
    ],
    "국가기관": [
        "국가계약법", "국가계약법 시행령", "국가계약법 시행규칙",
    ],
    "공기업·준정부기관": [
        "공기업계약사무규칙",
        "국가계약법", "국가계약법 시행령", "국가계약법 시행규칙",
    ],
}

# 모든 기관에 공통으로 포함되는 법령
COMMON_LAWS = [
    "중소기업구매촉진법", "중소기업구매촉진법 시행령", "중소기업구매촉진법 시행규칙",
    "조달사업법", "조달사업법 시행령", "조달사업법 시행규칙",
]


# ─────────────────────────────────────────────
# 법률 도메인 토크나이저 (kiwipiepy 기반)
# ─────────────────────────────────────────────
_kiwi = None  # 지연 초기화 (import 시 로드 방지)

def _get_kiwi():
    """Kiwi 형태소 분석기 싱글턴 (사용자 사전 포함)."""
    global _kiwi
    if _kiwi is not None:
        return _kiwi

    from kiwipiepy import Kiwi
    _kiwi = Kiwi()

    # 법률 도메인 사용자 사전: 복합 명사를 하나의 토큰으로 유지
    # score를 높게 설정하여 기본 사전보다 우선 적용
    legal_terms = [
        # ① 계약 방식 및 제도
        "수의계약", "제한경쟁", "지명경쟁", "일반경쟁", "협상계약",
        "공동수급", "공동수급체", "공동도급", "하도급",
        "제3자단가계약", "다수공급자계약", "카탈로그계약", "개산계약",
        "장기계속계약", "단년도차수계약",
        "일반경쟁입찰", "제한경쟁입찰", "지명경쟁입찰",
        "희망수량경쟁입찰", "2단계경쟁입찰",
        "설계시공일괄입찰", "대안입찰", "기술제안입찰",
        "협상에의한계약", "경쟁적대화",
        "시범구매제도", "우수조달공동상표", "벤처나라",
        "지역제한입찰",

        # ② 인증 및 기술 소명
        "신제품인증", "신기술인증", "우수품질소프트웨어",
        "성능인증", "우수재활용인증", "환경표지인증",
        "고효율에너지기자재", "품질보증조달물품", "혁신제품", "산업융합신제품",
        "재난안전제품", "녹색기술인증", "우수발명품",
        "우수조달물품", "직접생산확인",

        # ③ 제출 서류 및 평가 항목
        "직접생산확인증명서", "중소기업확인서", "신용평가등급확인서",
        "구성대비표", "제품규격서", "기술성능비교표", "원가계산보고서",
        "사적이해관계자신고서약서", "신인도심사", "연장기간평가", "종합평가",
        "시험성적서", "설치시방서",
        "적격심사", "제안서평가", "최저가낙찰", "가격입찰", "기술평가",

        # ④ 가격 및 비용 관련
        "추정가격", "예정가격", "기초금액", "수의시담", "낙찰차액",
        "직접재료비", "직접노무비", "간접노무비", "제조원가",
        "일반관리비", "이윤",
        "입찰보증금", "계약보증금", "하자보수보증금", "지연배상금",
        "품목조정률", "지수조정률", "선금급", "기성대가",
        "계약금액", "설계변경", "이행보증",

        # ⑤ 기구 및 조직
        "조달정책심의위원회", "지방건설기술심의위원회", "계약심의위원회",
        "혁신제품지원센터", "조달기업공제조합",

        # 지역 관련
        "지역제한", "지역업체", "지역상생", "지역상품", "우선구매",
        "사회적경제기업", "지역산물",

        # 기업 유형
        "소기업", "소상공인", "중소기업", "사회적기업", "여성기업",
        "장애인기업", "중소벤처",

        # 법령 약칭 및 규칙
        "지방계약법", "국가계약법", "조달사업법", "판로지원법",
        "한시적특례", "계약사무규칙", "집행기준", "계약예규",
        "과업지시서", "시방서",

        # 기관 유형
        "지방자치단체", "출자출연기관", "준정부기관", "공기업",

        # 기타
        "입찰공고", "낙찰자", "종합쇼핑몰",
    ]
    for term in legal_terms:
        _kiwi.add_user_word(term, "NNG", score=30.0)

    return _kiwi


# 복합명사 복원용 집합 (Kiwi가 분리할 경우 후처리로 재결합)
_COMPOUND_NOUNS = {
    ("수의", "계약"): "수의계약",
    ("지역", "제한"): "지역제한",
    ("지역", "업체"): "지역업체",
    ("입찰", "공고"): "입찰공고",
    ("적격", "심사"): "적격심사",
    ("종합", "평가"): "종합평가",
    ("추정", "가격"): "추정가격",
    ("예정", "가격"): "예정가격",
    ("계약", "금액"): "계약금액",
    ("우선", "구매"): "우선구매",
}

def _legal_tokenize(text: str) -> list[str]:
    """
    법률 텍스트 형태소 분석: 명사(N*)·숫자(SN)·외국어(SL) 추출 + 조항 번호 보존.
    """
    tokens = []

    # 1. 조항 번호 패턴 먼저 추출 (제N조, 제N항, 제N호)
    import re
    article_patterns = re.findall(r'제\d+조(?:의\d+)?|제\d+항|제\d+호', text)
    tokens.extend(article_patterns)

    # 2. Kiwi 형태소 분석 (명사·숫자 위주 추출)
    raw_tokens = []
    try:
        kiwi = _get_kiwi()
        result = kiwi.analyze(text)
        if result:
            for token in result[0][0]:
                word = token[0]
                tag = token[1]
                # 명사류(NNG, NNP, NNB), 숫자(SN), 외국어(SL)
                if tag.startswith('N') or tag in ('SN', 'SL'):
                    if len(word) >= 2:  # 1글자 토큰 제외 (노이즈 방지)
                        raw_tokens.append(word)
    except Exception:
        # Kiwi 실패 시 공백 분리 fallback
        raw_tokens = [t for t in text.split() if len(t) >= 2]

    # 3. 복합명사 후처리: 분리된 토큰 재결합
    i = 0
    while i < len(raw_tokens):
        if i + 1 < len(raw_tokens):
            pair = (raw_tokens[i], raw_tokens[i + 1])
            if pair in _COMPOUND_NOUNS:
                tokens.append(_COMPOUND_NOUNS[pair])
                i += 2
                continue
        tokens.append(raw_tokens[i])
        i += 1

    return tokens if tokens else text.split()


def search_laws(query: str, n_results: int = 5, agency_type: str = None) -> list[dict]:
    """
    진정한 하이브리드 법령 RAG 검색.
    Vector(ChromaDB) Top 30 + BM25(전역 인덱스) Top 30 → RRF 병합 → Top N
    
    Args:
        query: 검색어 (예: "수의계약 한도", "제25조")
        n_results: 반환 개수
        agency_type: 소속기관 유형. None이면 필터 없이 전체 검색.
    """
    POOL_SIZE = 30  # 각 엔진에서 추출할 후보 수
    RRF_K = 60      # RRF 상수

    # ─── 인덱스 정합성 Watchdog ───
    # ChromaDB와 BM25 pickle의 수정시간 차이가 1시간 이상이면 경고
    try:
        chroma_db_path = os.path.join(CHROMA_DIR, "chroma.sqlite3")
        if os.path.exists(chroma_db_path) and os.path.exists(BM25_INDEX_PATH):
            chroma_mtime = os.path.getmtime(chroma_db_path)
            bm25_mtime = os.path.getmtime(BM25_INDEX_PATH)
            drift = abs(chroma_mtime - bm25_mtime)
            if drift > 3600:  # 1시간 = 3600초
                import logging
                logging.warning(
                    f"[INDEX SYNC] ChromaDB-BM25 drift: {drift/3600:.1f}h. "
                    f"Run 'python ingest_laws.py' to resync."
                )
    except Exception:
        pass

    # 기관 유형별 필터
    target_laws = None
    if agency_type and agency_type in AGENCY_LAW_MAP:
        target_laws = set(AGENCY_LAW_MAP[agency_type] + COMMON_LAWS)

    # ─── 경로 1: Vector 검색 (ChromaDB, 의미 유사도) ───
    vector_hits = {}  # doc_id -> {rank, doc, meta, distance}
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn_query,
        )

        where_filter = {"law_short": {"$in": list(target_laws)}} if target_laws else None
        vr = collection.query(
            query_texts=[query],
            n_results=POOL_SIZE,
            where=where_filter,
        )

        # fallback: 필터 결과 0건이면 필터 해제
        if where_filter and (not vr["documents"] or not vr["documents"][0]):
            vr = collection.query(query_texts=[query], n_results=POOL_SIZE)

        if vr["documents"] and vr["documents"][0]:
            for rank, (doc_id, doc, meta, dist) in enumerate(zip(
                vr["ids"][0], vr["documents"][0], vr["metadatas"][0],
                vr["distances"][0] if vr.get("distances") else [0]*len(vr["ids"][0])
            )):
                vector_hits[doc_id] = {
                    "rank": rank, "doc": doc, "meta": meta, "distance": dist,
                }
    except Exception as e:
        print(f"  [Vector] 검색 실패: {e}")

    # ─── 경로 2: BM25 검색 (전역 인덱스, 키워드 매칭) ───
    bm25_hits = {}  # doc_id -> {rank, doc, meta, score}
    try:
        with open(BM25_INDEX_PATH, "rb") as f:
            index_data = pickle.load(f)

        bm25 = index_data["bm25"]
        all_ids = index_data["ids"]
        all_docs = index_data["documents"]
        all_metas = index_data["metadatas"]

        tokenized_query = _legal_tokenize(query)
        scores = bm25.get_scores(tokenized_query)

        # 점수 높은 순 정렬
        sorted_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        rank = 0
        for idx in sorted_indices:
            if rank >= POOL_SIZE:
                break

            # 기관 필터 적용 (Pre-filtering)
            if target_laws:
                law_short = all_metas[idx].get("law_short", "")
                if law_short not in target_laws:
                    continue

            doc_id = all_ids[idx]
            bm25_hits[doc_id] = {
                "rank": rank,
                "doc": all_docs[idx],
                "meta": all_metas[idx],
                "score": float(scores[idx]),
            }
            rank += 1

    except FileNotFoundError:
        print(f"  [BM25] 인덱스 없음 — 벡터 검색만 사용. 'python ingest_laws.py' 실행 필요.")
    except Exception as e:
        print(f"  [BM25] 검색 실패: {e}")

    # ─── 가중 RRF 병합: 두 경로의 순위 결합 ───
    # E5 임베딩 강화에 따라 Vector에 더 높은 가중치 부여
    W_VECTOR = 0.6   # 의미론적 검색 (E5)
    W_BM25 = 0.4     # 키워드 매칭 (BM25)

    all_doc_ids = set(vector_hits.keys()) | set(bm25_hits.keys())

    if not all_doc_ids:
        return []

    rrf_scores = []
    for doc_id in all_doc_ids:
        score = 0.0
        v = vector_hits.get(doc_id)
        b = bm25_hits.get(doc_id)

        # rank는 0-indexed → +1 보정 (표준 RRF 수식: 1부터 시작)
        if v:
            score += W_VECTOR * (1.0 / (RRF_K + v["rank"] + 1))
        if b:
            score += W_BM25 * (1.0 / (RRF_K + b["rank"] + 1))

        # 문서 정보 (Vector 우선, 없으면 BM25)
        hit = v or b
        rrf_scores.append((doc_id, score, hit))

    # RRF 점수 높은 순 정렬
    rrf_scores.sort(key=lambda x: x[1], reverse=True)

    law_results = []
    for doc_id, score, hit in rrf_scores[:n_results]:
        meta = hit["meta"]
        law_results.append({
            "law": meta.get("law_short", ""),
            "article": meta.get("article_no", ""),
            "title": meta.get("article_title", ""),
            "text": hit["doc"],
            "tier": meta.get("tier", ""),
            "distance": hit.get("distance", 0),
            "rrf_score": round(score, 6),
            "source": ("both" if doc_id in vector_hits and doc_id in bm25_hits
                       else "vector" if doc_id in vector_hits else "bm25"),
        })

    return law_results


def check_status() -> dict:
    """적재된 법령 현황 확인."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn_passage,
        )
        existing = collection.get(include=["metadatas"])
        laws = {}
        for meta in existing.get("metadatas", []):
            short = meta.get("law_short", "")
            if short and short not in laws:
                laws[short] = meta.get("enforcement_date", "")
        return {"total": collection.count(), "laws": laws}
    except Exception:
        return {"total": 0, "laws": {}}


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    test_mode = "--test" in sys.argv
    update_mode = "--update" in sys.argv
    check_mode = "--check" in sys.argv

    print("=" * 50)
    print("핵심 법령 RAG 적재 시스템")
    print("=" * 50)

    if check_mode:
        print("\n[적재 현황]")
        status = check_status()
        print(f"  총 문서: {status['total']}건")
        for name, date in status["laws"].items():
            print(f"  - {name}: {date}")
        sys.exit(0)

    if test_mode:
        # 지방계약법 시행령 1건만 MCP 테스트
        print("\n[TEST] 지방계약법 시행령 조문 수집 (MCP)...")
        articles = fetch_law_articles_via_mcp("281055")
        print(f"  -> {len(articles)} chunks")
        if articles:
            print(f"\n  [0] {articles[0]['조번호']} {articles[0]['조제목']}")
            print(f"  {articles[0]['조문전체'][:300]}...")
        sys.exit(0)

    if update_mode:
        print("mode: UPDATE (개정된 법령만 재적재)\n")
    else:
        print("mode: FULL (전체 재적재)\n")

    ingest_laws(update_mode=update_mode)

    # 테스트 검색
    print(f"\n{'='*50}")
    print("테스트 검색: '수의계약 한도'")
    print("=" * 50)
    results = search_laws("수의계약 한도", n_results=3)
    for i, r in enumerate(results):
        print(f"\n[{i+1}] [{r['law']}] {r['article']} {r['title']}")
        print(f"    거리: {r['distance']:.4f}")
        print(f"    내용: {r['text'][:200]}...")
