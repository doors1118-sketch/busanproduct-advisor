"""
계약 매뉴얼 PDF → ChromaDB RAG 적재 스크립트
E5 임베딩(intfloat/multilingual-e5-large) 사용
"""
import os
import sys
import hashlib
import fitz  # PyMuPDF
import chromadb
from embedding import get_passage_embedding_fn, get_query_embedding_fn

# ─────────────────────────────────────────────
# 설정
# ─────────────────────────────────────────────
import json
from dotenv import load_dotenv

load_dotenv()

_root = os.path.dirname(os.path.abspath(__file__))
CHROMA_DIR = os.getenv("CHROMA_MANUALS_DIR", os.path.join(_root, ".chroma_manuals"))
COLLECTION_NAME = "manuals"

# 적재 대상 디렉터리 (PDF 파일)
MANUAL_DIRS = [
    os.path.join(os.path.dirname(_root), "계약메뉴얼"),  # 핵심 매뉴얼
]

# 프로젝트 루트의 개별 PDF 파일 (조달청 규정 등)
EXTRA_PDFS = [
    os.path.join(os.path.dirname(_root), f)
    for f in [
        "물품 다수공급자계약 업무처리규정(조달청훈령)(제2373호)(20260227).pdf",
        "용역 다수공급자계약 업무처리규정(조달청고시)(제2026-1호)(20260201).pdf",
        "용역 카탈로그 계약 업무처리규정(조달청고시)(제2026-2호)(20260201).pdf",
        "물품구매(제조)계약 특수조건(조달청지침)(제7356호)(20260101).pdf",
        "조달청 경쟁적 대화에 의한 계약체결 세부기준(조달청지침)(제403호)(20200401).pdf",
        "혁신제품 제3자단가계약 추가특수조건(조달청공고)(제2026-90호)(20260227).pdf",
        "다수공급자계약 추가특수조건(조달청공고)(제2016-22호)(20160301).pdf",
        "디지털서비스 카탈로그계약 특수조건(조달청공고)(제2025-531호)(20260101).pdf",
        "복수물품 공급계약업무 처리규정(조달청훈령)(제2329호)(20260123).pdf",
        "상용소프트웨어 다수공급자계약 업무처리규정(조달청훈령)(제2290호)(20250901).pdf",
        "물품구매계약 품질관리 특수조건(조달청지침)(제1635호)(20260316).pdf",
        "상용소프트웨어 다수공급자계약 특수조건(조달청공고)(제2025-532호)(20260101).pdf",
        "지방자치단체 입찰 및 계약집행기준(행정안전부예규)(제332호)(20250708).pdf",
        "(붙임1) 중소벤처기업부 시범구매제도 안내.pdf",
    ]
]

# 청크 설정
CHUNK_SIZE = 800      # 글자 수 기준 (E5 최대 512토큰 ≈ 한국어 ~800자)
CHUNK_OVERLAP = 100   # 오버랩


# ─────────────────────────────────────────────
# PDF 텍스트 추출
# ─────────────────────────────────────────────
def extract_text_from_pdf(pdf_path: str, error_log: dict = None) -> list[dict]:
    """PDF에서 페이지별 텍스트 추출."""
    pages = []
    try:
        doc = fitz.open(pdf_path)
        for i, page in enumerate(doc):
            text = page.get_text().strip()
            if len(text) > 30:  # 의미 있는 텍스트만
                pages.append({
                    "text": text,
                    "page": i + 1,
                    "source": os.path.basename(pdf_path),
                })
        doc.close()
    except Exception as e:
        print(f"  [WARN] PDF read failed: {pdf_path} - {e}")
        if error_log is not None:
            error_log[pdf_path] = str(e)
    return pages


# ─────────────────────────────────────────────
# 텍스트 청크 분할
# ─────────────────────────────────────────────
def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """텍스트를 의미 단위(문단/문장)로 청크 분할."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size

        # 청크 끝을 문장 경계(. 또는 \n)에 맞춤
        if end < len(text):
            # 마지막 줄바꿈 또는 마침표 위치 찾기
            last_break = text.rfind('\n', start + chunk_size // 2, end)
            if last_break == -1:
                last_break = text.rfind('. ', start + chunk_size // 2, end)
            if last_break > start:
                end = last_break + 1

        chunks.append(text[start:end].strip())
        start = end - overlap

    return [c for c in chunks if len(c) > 30]


# ─────────────────────────────────────────────
# ChromaDB 적재
# ─────────────────────────────────────────────
def _get_existing_sources(collection) -> set:
    """컬렉션에 이미 적재된 PDF 파일명 목록 조회."""
    try:
        all_meta = collection.get(include=["metadatas"])
        sources = set()
        if all_meta and all_meta.get("metadatas"):
            for meta in all_meta["metadatas"]:
                if meta and "source" in meta:
                    sources.add(meta["source"])
        return sources
    except Exception:
        return set()


def _delete_source_chunks(collection, source_name: str) -> int:
    """특정 PDF의 청크를 컬렉션에서 삭제."""
    try:
        results = collection.get(
            where={"source": source_name},
            include=["metadatas"],
        )
        if results and results.get("ids"):
            ids_to_delete = results["ids"]
            collection.delete(ids=ids_to_delete)
            return len(ids_to_delete)
    except Exception:
        pass
    return 0


def ingest_manuals(mode: str = "full", target_pdfs: list[str] = None):
    """
    매뉴얼 PDF를 ChromaDB에 적재.

    Args:
        mode:
          - "full": 전체 삭제 후 재적재 (기존 방식)
          - "add": 신규 PDF만 추가 (이미 적재된 PDF는 스킵)
          - "replace": 특정 PDF 교체 (구판 삭제 → 신판 추가)
        target_pdfs: replace 모드에서 교체할 PDF 파일 경로 리스트
    """
    print("=" * 50)
    print(f"  Manual RAG Ingest (mode: {mode})")
    print("=" * 50)

    # 1. PDF 파일 목록 수집
    pdf_files = []
    for d in MANUAL_DIRS:
        if os.path.isdir(d):
            for f in os.listdir(d):
                if f.lower().endswith('.pdf'):
                    pdf_files.append(os.path.join(d, f))

    for f in EXTRA_PDFS:
        if os.path.isfile(f):
            pdf_files.append(f)

    if not pdf_files:
        print("  [SKIP] No PDF files found. Skipping manuals RAG ingestion.")
        return

    # 2. ChromaDB 준비
    embedding_fn = get_passage_embedding_fn()
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    if mode == "full":
        # 전체 재적재: 기존 삭제
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"  Deleted existing '{COLLECTION_NAME}' collection")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
        metadata={"description": "contracts manuals & procurement guidelines"},
    )

    # 3. 모드별 처리
    if mode == "add":
        # 증분 적재: 이미 적재된 PDF 스킵
        existing = _get_existing_sources(collection)
        new_pdfs = [p for p in pdf_files if os.path.basename(p) not in existing]
        skipped = len(pdf_files) - len(new_pdfs)
        print(f"  Found {len(pdf_files)} PDFs total, {skipped} already loaded, {len(new_pdfs)} new\n")
        pdf_files = new_pdfs
        if not pdf_files:
            print(f"  [DONE] No new PDFs to add. Collection: {collection.count()} docs")
            return

    elif mode == "replace":
        # 교체 모드: 지정된 PDF만 처리
        if target_pdfs:
            pdf_files = [p for p in pdf_files if os.path.basename(p) in target_pdfs
                         or p in target_pdfs]
        for pdf_path in pdf_files:
            fname = os.path.basename(pdf_path)
            deleted = _delete_source_chunks(collection, fname)
            if deleted:
                print(f"  [REPLACE] {fname}: deleted {deleted} old chunks")
        print(f"  Replacing {len(pdf_files)} PDFs\n")

    else:
        print(f"  Found {len(pdf_files)} PDF files\n")

    # 4. 텍스트 추출 + 청크 분할
    all_chunks = []
    error_log = {}
    for pdf_path in pdf_files:
        fname = os.path.basename(pdf_path)
        pages = extract_text_from_pdf(pdf_path, error_log)
        if not pages:
            print(f"  [SKIP] {fname} (no text)")
            continue

        chunk_count = 0
        for page_info in pages:
            chunks = chunk_text(page_info["text"])
            for ci, chunk in enumerate(chunks):
                doc_id = hashlib.md5(
                    f"{fname}_p{page_info['page']}_c{ci}".encode()
                ).hexdigest()

                all_chunks.append({
                    "id": doc_id,
                    "text": chunk,
                    "metadata": {
                        "source": fname,
                        "page": page_info["page"],
                        "chunk": ci,
                    },
                })
                chunk_count += 1

        print(f"  [OK] {fname}: {len(pages)} pages -> {chunk_count} chunks")

    print(f"\n  Total: {len(all_chunks)} chunks from {len(pdf_files)} PDFs\n")

    if error_log:
        error_file = os.path.join(_root, "pymupdf_error_log.json")
        with open(error_file, "w", encoding="utf-8") as f:
            json.dump(error_log, f, ensure_ascii=False, indent=2)
        print(f"  [WARN] Logged {len(error_log)} PyMuPDF errors to {error_file}")

    if not all_chunks:
        print(f"  [DONE] No new chunks. Collection: {collection.count()} docs")
        return

    # 5. 배치 적재 (50건씩)
    batch_size = 50
    for i in range(0, len(all_chunks), batch_size):
        batch = all_chunks[i:i + batch_size]
        collection.upsert(
            ids=[c["id"] for c in batch],
            documents=[c["text"] for c in batch],
            metadatas=[c["metadata"] for c in batch],
        )
        print(f"  Ingested: {min(i + batch_size, len(all_chunks))}/{len(all_chunks)}")

    print(f"\n  [DONE] manuals collection: {collection.count()} docs")


# ─────────────────────────────────────────────
# 검색 함수 (gemini_engine에서 호출)
# ─────────────────────────────────────────────
def search_manuals(query: str, n_results: int = 3) -> list[dict]:
    """매뉴얼 RAG 검색."""
    try:
        embedding_fn = get_query_embedding_fn()
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )

        results = collection.query(
            query_texts=[query],
            n_results=n_results,
        )

        if not results["documents"] or not results["documents"][0]:
            return []

        return [
            {
                "text": doc,
                "source": meta.get("source", ""),
                "page": meta.get("page", "?"),
            }
            for doc, meta in zip(results["documents"][0], results["metadatas"][0])
        ]
    except Exception:
        return []


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="매뉴얼 RAG 적재")
    parser.add_argument("--mode", choices=["full", "add", "replace"], default="add",
                        help="적재 모드: full(전체 재적재), add(신규만 추가), replace(교체)")
    parser.add_argument("--files", nargs="*", default=None,
                        help="replace 모드에서 교체할 PDF 파일명(들)")
    args = parser.parse_args()
    ingest_manuals(mode=args.mode, target_pdfs=args.files)
