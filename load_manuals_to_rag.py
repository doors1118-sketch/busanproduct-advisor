"""
계약 매뉴얼 PDF → ChromaDB manuals 컬렉션 적재 스크립트

1. PDF에서 텍스트 추출 (fitz/PyMuPDF)
2. 적절한 청크로 분할 (800자, 200자 오버랩)
3. ChromaDB manuals 컬렉션에 적재
"""
import os
import sys
sys.stdout.reconfigure(encoding='utf-8')

import fitz  # PyMuPDF
import chromadb
from chromadb.utils import embedding_functions

# ─── 설정 ───
MANUAL_DIR = r"C:\Users\COMTREE\Desktop\메뉴얼 제작\계약메뉴얼"
CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", ".chroma")
COLLECTION_NAME = "manuals"
CHUNK_SIZE = 800      # 청크 크기 (글자 수)
CHUNK_OVERLAP = 200   # 오버랩 (글자 수)

# 1차 적재 대상 (핵심 4개)
PRIORITY_FILES = [
    "(1권) 2025 공공구매제도 실무가이드.pdf",
    "(25.9.15)지방계약 실무 매뉴얼.pdf",
    "2025 조합추천수의계약 제도 안내자료.pdf",
    "★2025 소기업공동사업제품우선구매 안내자료(6.17).pdf",
]

def extract_text_from_pdf(pdf_path: str) -> list[dict]:
    """PDF에서 페이지별 텍스트 추출"""
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if len(text) > 30:  # 너무 짧은 페이지 (이미지만) 제외
            pages.append({
                "page": i + 1,
                "text": text,
            })
    doc.close()
    return pages


def chunk_text(text: str, source: str, page: int) -> list[dict]:
    """텍스트를 청크로 분할"""
    chunks = []
    start = 0
    chunk_idx = 0
    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end]
        if len(chunk.strip()) > 50:  # 너무 짧은 청크 제외
            chunks.append({
                "text": chunk,
                "source": source,
                "page": page,
                "chunk_idx": chunk_idx,
            })
            chunk_idx += 1
        start = end - CHUNK_OVERLAP
    return chunks


def main():
    # ─── ChromaDB 연결 ───
    print("ChromaDB 연결 중...")
    ef = embedding_functions.DefaultEmbeddingFunction()
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    
    # 기존 manuals 컬렉션 삭제 후 재생성
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"기존 '{COLLECTION_NAME}' 컬렉션 삭제")
    except Exception:
        pass
    
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"description": "계약 매뉴얼 RAG"}
    )
    
    total_chunks = 0
    
    for filename in PRIORITY_FILES:
        filepath = os.path.join(MANUAL_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  ❌ 파일 없음: {filename}")
            continue
        
        short_name = filename.replace(".pdf", "")
        print(f"\n📄 처리 중: {short_name}")
        
        # 1. 텍스트 추출
        pages = extract_text_from_pdf(filepath)
        print(f"  → {len(pages)}페이지에서 텍스트 추출")
        
        if not pages:
            print(f"  ⚠️ 텍스트 없음 (이미지 PDF?) — 건너뛰기")
            continue
        
        # 2. 청크 분할
        all_chunks = []
        for p in pages:
            chunks = chunk_text(p["text"], short_name, p["page"])
            all_chunks.extend(chunks)
        
        print(f"  → {len(all_chunks)}개 청크 생성")
        
        # 3. ChromaDB 적재 (배치)
        batch_size = 50
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            ids = [f"manual_{short_name[:20]}_{c['page']}_{c['chunk_idx']}" for c in batch]
            docs = [c["text"] for c in batch]
            metas = [{"source": c["source"], "page": c["page"], "type": "manual"} for c in batch]
            
            collection.add(
                ids=ids,
                documents=docs,
                metadatas=metas,
            )
        
        total_chunks += len(all_chunks)
        print(f"  ✅ {len(all_chunks)}개 청크 적재 완료")
    
    print(f"\n{'='*50}")
    print(f"✅ 총 {total_chunks}개 청크 → '{COLLECTION_NAME}' 컬렉션 적재 완료")
    print(f"ChromaDB 경로: {CHROMA_DIR}")


if __name__ == "__main__":
    main()
