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
import time
import chromadb
from chromadb.utils import embedding_functions
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

embedding_fn = embedding_functions.DefaultEmbeddingFunction()

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
        embedding_function=embedding_fn,
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


# ─────────────────────────────────────────────
# RAG 검색 함수 (gemini_engine에서 호출)
# ─────────────────────────────────────────────

def search_laws(query: str, n_results: int = 5) -> list[dict]:
    """
    법령 RAG 검색. 질의와 유사한 조문 반환.
    
    Args:
        query: 검색어 (예: "수의계약 한도")
        n_results: 반환 개수
    
    Returns:
        [{"law": "지방계약법 시행령", "article": "제25조", "title": "...", "text": "..."}, ...]
    """
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
    except Exception:
        return []  # 컬렉션 없으면 빈 리스트

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
    )

    law_results = []
    for i, (doc, meta) in enumerate(zip(
        results["documents"][0],
        results["metadatas"][0]
    )):
        law_results.append({
            "law": meta.get("law_short", ""),
            "article": meta.get("article_no", ""),
            "title": meta.get("article_title", ""),
            "text": doc,
            "tier": meta.get("tier", ""),
            "distance": results["distances"][0][i] if results.get("distances") else None,
        })

    return law_results


def check_status() -> dict:
    """적재된 법령 현황 확인."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
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
