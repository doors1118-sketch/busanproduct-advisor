"""
혁신제품 데이터 ChromaDB 적재 + 검색
- Excel → E5 임베딩 → innovation 컬렉션
- 메타데이터: 사업자번호, 업체명, 소재지, 세부품명번호, 혁신구분, 희망가격, 지정연도
- 검색: 의미(Vector) + 메타데이터 필터 (UNSPSC, 가격, 만료여부)
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import re
import pandas as pd
import chromadb
from embedding import get_passage_embedding_fn, get_query_embedding_fn

CHROMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".chroma")
COLLECTION_NAME = "innovation"
EXCEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "..", "혁신제품 전체보기 20260423 153055.xlsx")


def _extract_year(cert_no: str) -> int:
    """지정서인증번호에서 지정연도 추출. 예: '2024-390' → 2024"""
    m = re.match(r"(\d{4})", str(cert_no))
    return int(m.group(1)) if m else 0


def _is_valid(cert_no: str, valid_years: int = 3) -> bool:
    """혁신제품 지정이 아직 유효한지 확인 (3년 기준)"""
    from datetime import datetime
    year = _extract_year(cert_no)
    if year == 0:
        return True  # 파싱 불가 시 유효로 간주
    return (datetime.now().year - year) < valid_years


def ingest_innovation():
    """Excel → ChromaDB innovation 컬렉션 적재"""
    print("=" * 50)
    print("  Innovation Product RAG Ingest")
    print("=" * 50)

    # Excel 로드
    df = pd.read_excel(EXCEL_PATH)
    print(f"  Loaded: {len(df)} rows, {df['업체명'].nunique()} companies")

    # ChromaDB 준비
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # 기존 컬렉션 삭제 후 재생성
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"  Deleted existing '{COLLECTION_NAME}' collection")
    except Exception:
        pass

    embedding_fn = get_passage_embedding_fn()
    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_fn,
    )

    # 문서 생성 + 메타데이터
    ids, documents, metadatas = [], [], []
    skipped = 0

    for idx, row in df.iterrows():
        cert_no = str(row.get("지정서인증번호", ""))

        # 만료 제품 제외 (3년 초과)
        if not _is_valid(cert_no):
            skipped += 1
            continue

        # 검색용 텍스트: 상품명 + 모델명 + 상품설명 결합
        product_name = str(row.get("상품명", ""))
        model = str(row.get("모델명", ""))
        description = str(row.get("상품설명", ""))
        company = str(row.get("업체명", ""))

        doc_text = f"[혁신제품] {product_name}"
        if model and model != "nan":
            doc_text += f" (모델: {model})"
        if description and description != "nan":
            doc_text += f"\n{description[:500]}"

        # 메타데이터
        price = row.get("희망가격", 0)
        if pd.isna(price):
            price = 0

        meta = {
            "company": company,
            "biz_no": str(row.get("사업자번호", "")),
            "location": str(row.get("업체소재지", "")),
            "product_name": product_name,
            "model": model if model != "nan" else "",
            "item_code": str(row.get("세부품명번호", "")),
            "cert_no": cert_no,
            "cert_year": _extract_year(cert_no),
            "innovation_type": str(row.get("혁신제품 구분", "")),
            "agency": str(row.get("지정기관", "")),
            "price": int(price),
            "unit": str(row.get("단위", "")),
        }

        ids.append(f"innov_{idx}")
        documents.append(doc_text)
        metadatas.append(meta)

    print(f"  Valid products: {len(ids)} (skipped expired: {skipped})")

    # 배치 적재 (50건씩)
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        end = min(i + batch_size, len(ids))
        collection.add(
            ids=ids[i:end],
            documents=documents[i:end],
            metadatas=metadatas[i:end],
        )
        if (i + batch_size) % 200 == 0 or end == len(ids):
            print(f"  Ingested: {end}/{len(ids)}")

    print(f"\n  [DONE] innovation collection: {collection.count()} docs")
    return collection.count()


def search_innovation(query: str, n_results: int = 5,
                      max_price: int = None,
                      item_code: str = None,
                      innovation_type: str = None) -> str:
    """
    혁신제품 검색 (의미 검색 + 메타데이터 필터).

    Args:
        query: 검색어 (예: "배전반", "CCTV", "공기청정기")
        n_results: 반환 건수
        max_price: 최대 가격 필터 (원)
        item_code: 세부품명번호(UNSPSC) 필터
        innovation_type: "유형1" 또는 "유형2" 필터
    """
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        embedding_fn = get_query_embedding_fn()
        collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
    except Exception:
        return ""

    # where 필터 구성
    where_clauses = []
    if max_price:
        where_clauses.append({"price": {"$lte": max_price}})
    if item_code:
        where_clauses.append({"item_code": {"$eq": item_code}})
    if innovation_type:
        where_clauses.append({"innovation_type": {"$eq": innovation_type}})

    where_filter = None
    if len(where_clauses) == 1:
        where_filter = where_clauses[0]
    elif len(where_clauses) > 1:
        where_filter = {"$and": where_clauses}

    # 검색
    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where_filter,
    )

    if not results["documents"][0]:
        return ""

    # 포맷팅
    lines = ["[혁신제품 검색 결과]"]
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        company = meta.get("company", "")
        product = meta.get("product_name", "")
        model = meta.get("model", "")
        innov_type = meta.get("innovation_type", "")
        price = meta.get("price", 0)
        location = meta.get("location", "")
        cert_no = meta.get("cert_no", "")

        price_str = f"{price:,}원" if price > 0 else "가격 미정"
        line = f"- {product}"
        if model:
            line += f" ({model})"
        line += f"\n  업체: {company} | 소재지: {location}"
        line += f"\n  구분: {innov_type} | 인증번호: {cert_no} | 희망가격: {price_str}"
        lines.append(line)

    lines.append(f"\n* 혁신제품은 수의계약 검토 후보입니다. 지정 유효기간, 혁신장터 등록 여부, 수요기관 적용 법령 확인이 필요합니다.")
    return "\n".join(lines)


# ─────────────────────────────────────────
if __name__ == "__main__":
    ingest_innovation()
