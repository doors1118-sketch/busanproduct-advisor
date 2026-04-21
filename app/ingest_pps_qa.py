"""
조달청 종합민원센터 질의응답 해석사례 — RAG 데이터 수집 + ChromaDB 적재
공공데이터포털 API에서 867건 다운로드 → 벡터DB에 임베딩 저장.

사용법:
    python ingest_pps_qa.py          # 최초 적재
    python ingest_pps_qa.py --update # 신규 데이터만 추가
"""
import os
import json
import time
import requests
import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
API_BASE = "https://api.odcloud.kr/api/15146890/v1/uddi:793a1c82-8641-49eb-b4e9-e7bc4529827d"
SERVICE_KEY = "c551b235466f84865b201c21869bc5b08cdf0633cdb4a3105dfb1e19c6427865"
PER_PAGE = 100  # 한 번에 가져오는 건수

# ChromaDB 설정
CHROMA_DIR = os.path.join(os.path.dirname(__file__), ".chroma")
COLLECTION_NAME = "pps_qa"

# 임베딩 함수 (다국어 지원 — 한국어 최적)
embedding_fn = embedding_functions.DefaultEmbeddingFunction()


def fetch_all_data() -> list[dict]:
    """API에서 전체 데이터 수집."""
    all_data = []
    page = 1

    while True:
        print(f"  페이지 {page} 수집 중...")
        resp = requests.get(API_BASE, params={
            "page": page,
            "perPage": PER_PAGE,
            "serviceKey": SERVICE_KEY,
        }, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        data = result.get("data", [])
        if not data:
            break

        all_data.extend(data)
        total = result.get("totalCount", 0)
        print(f"  → {len(all_data)} / {total} 건")

        if len(all_data) >= total:
            break

        page += 1
        time.sleep(0.3)  # API 부하 방지

    return all_data


def ingest_to_chroma(data: list[dict], update_mode: bool = False):
    """ChromaDB에 데이터 적재."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if not update_mode:
        # 기존 컬렉션 삭제 후 재생성
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"description": "조달청 종합민원센터 질의응답 해석사례"},
    )

    # 기존 ID 확인 (업데이트 모드)
    existing_ids = set()
    if update_mode:
        existing = collection.get()
        existing_ids = set(existing["ids"])
        print(f"  기존 {len(existing_ids)}건 존재")

    # 데이터 적재
    ids = []
    documents = []
    metadatas = []
    skipped = 0

    for item in data:
        doc_id = f"pps_{item.get('공개번호', item.get('순번', ''))}"

        if update_mode and doc_id in existing_ids:
            skipped += 1
            continue

        # 질의 + 회신을 하나의 문서로 결합
        question = item.get("질의내용", "")
        answer = item.get("회신내용", "")
        title = item.get("제목", "")

        # 검색용 문서: 제목 + 질의내용 (임베딩 대상)
        doc_text = f"[{title}]\n질의: {question}"

        ids.append(doc_id)
        documents.append(doc_text)
        metadatas.append({
            "title": title,
            "question": question[:500],  # 메타데이터 크기 제한
            "answer": answer[:2000],
            "category": f"{item.get('대분류', '')} > {item.get('중분류', '')} > {item.get('소분류', '')}",
            "date": item.get("회신일자", ""),
            "public_no": str(item.get("공개번호", "")),
            "views": item.get("조회수", 0),
        })

    if not ids:
        print(f"  새로운 데이터 없음 (스킵: {skipped}건)")
        return

    # 배치 적재 (ChromaDB 제한: 한 번에 최대 5461건)
    batch_size = 500
    for i in range(0, len(ids), batch_size):
        batch_end = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:batch_end],
            documents=documents[i:batch_end],
            metadatas=metadatas[i:batch_end],
        )
        print(f"  적재: {batch_end}/{len(ids)} 건")

    print(f"\n✅ 총 {len(ids)}건 적재 완료 (스킵: {skipped}건)")
    print(f"   컬렉션 총 문서: {collection.count()}건")


def search_qa(query: str, n_results: int = 3) -> list[dict]:
    """질의와 유사한 Q&A 검색."""
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
    )

    qa_list = []
    for i, meta in enumerate(results["metadatas"][0]):
        qa_list.append({
            "title": meta.get("title", ""),
            "question": meta.get("question", ""),
            "answer": meta.get("answer", ""),
            "category": meta.get("category", ""),
            "date": meta.get("date", ""),
            "distance": results["distances"][0][i] if results.get("distances") else None,
        })

    return qa_list


# ─────────────────────────────────────────────
# 메인
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    update_mode = "--update" in sys.argv

    print("=" * 50)
    print("조달청 질의응답 해석사례 RAG 데이터 수집")
    print("=" * 50)

    if update_mode:
        print("모드: 업데이트 (신규 데이터만 추가)\n")
    else:
        print("모드: 전체 재적재\n")

    # 1. API에서 데이터 수집
    print("[1/2] API 데이터 수집...")
    data = fetch_all_data()
    print(f"  → 총 {len(data)}건 수집 완료\n")

    # 2. ChromaDB에 적재
    print("[2/2] ChromaDB 적재...")
    ingest_to_chroma(data, update_mode=update_mode)

    # 3. 테스트 검색
    print("\n" + "=" * 50)
    print("테스트 검색: '수의계약 한도'")
    print("=" * 50)
    results = search_qa("수의계약 한도", n_results=2)
    for i, r in enumerate(results):
        print(f"\n[{i+1}] {r['title']}")
        print(f"    분류: {r['category']}")
        print(f"    날짜: {r['date']}")
        print(f"    유사도: {r['distance']:.4f}")
        print(f"    질의: {r['question'][:100]}...")
