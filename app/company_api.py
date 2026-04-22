"""
부산 지역업체 검색 API 클라이언트
https://busanproduct.co.kr/docs

조달청 등록 부산 지역업체를 면허/품목/분류코드/제조업체로 검색.
인증 불필요, CORS 제한 없음.
"""
import requests
from typing import Optional
from urllib.parse import quote
import io

BASE_URL = "https://busanproduct.co.kr"
TIMEOUT = 10

# 최근 검색 결과 저장 (챗봇 UI에서 전체 목록 다운로드용)
last_search_results: dict = {}
last_search_query: str = ""


def _api_get(endpoint: str, params: dict) -> dict:
    """공통 GET 요청."""
    try:
        resp = requests.get(
            f"{BASE_URL}{endpoint}",
            params=params,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e), "검색결과수": 0, "업체목록": []}


def search_by_license(query: str) -> dict:
    """면허(업종)으로 업체 검색. 예: '전기공사', '소방'"""
    return _api_get("/api/company/license-search", {"q": query})


def search_by_product(query: str) -> dict:
    """대표품목으로 업체 검색. 예: 'LED조명', 'CCTV'"""
    return _api_get("/api/company/product-search", {"q": query})


def search_by_category(query: str) -> dict:
    """분류코드(UNSPSC) 또는 분류명으로 업체 검색. 예: '43', '소방설비'"""
    return _api_get("/api/company/category-search", {"q": query})


def search_manufacturers(query: str) -> dict:
    """제조업체 검색. 예: 'LED'"""
    return _api_get("/api/company/manufacturers", {"q": query})


def format_company_results(data: dict, max_results: int = 10) -> str:
    """
    API 결과를 Gemini가 답변에 포함할 수 있는 텍스트로 변환.
    개인정보(사업자번호, 대표자 등)는 제외하고 업체명/소재지/품목만 노출.
    """
    companies = data.get("업체목록", [])
    total = data.get("검색결과수", len(companies))
    
    if not companies:
        return "검색 결과가 없습니다."
    
    lines = [f"부산 지역업체 검색 결과: 총 {total}건 (상위 {min(max_results, len(companies))}건 표시)"]
    lines.append("")
    
    for i, c in enumerate(companies[:max_results]):
        name = c.get("업체명", "")
        area = c.get("소재지", "")
        product = c.get("대표품명", "")
        biz_type = c.get("업체구분", "")
        mfg = c.get("제조구분", "")
        
        line = f"{i+1}. {name}"
        if area:
            line += f" ({area})"
        if product:
            line += f" — {product}"
        if biz_type:
            line += f" [{biz_type}]"
        if mfg:
            line += f" ({mfg})"
        lines.append(line)
    
    if total > max_results:
        lines.append(f"\n... 외 {total - max_results}건")
    
    return "\n".join(lines)


def results_to_excel(data: dict = None) -> bytes:
    """
    검색 결과를 Excel 바이트로 변환.
    data가 None이면 last_search_results 사용.
    개인정보(사업자번호, 대표자 연락처) 제외.
    """
    import pandas as pd
    
    if data is None:
        data = last_search_results
    
    companies = data.get("업체목록", [])
    if not companies:
        return b""
    
    # 개인정보 제외 필드만 추출
    safe_fields = ["업체명", "소재지", "대표품명", "업체구분", "제조구분"]
    rows = []
    for c in companies:
        row = {field: c.get(field, "") for field in safe_fields}
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────
# 테스트
# ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    print("=== 품목 검색: LED ===")
    result = search_by_product("LED")
    print(format_company_results(result, max_results=5))
    
    print("\n=== 면허 검색: 전기공사 ===")
    result = search_by_license("전기공사")
    print(format_company_results(result, max_results=5))
    
    print("\n=== 분류코드 검색: 소방 ===")
    result = search_by_category("소방")
    print(format_company_results(result, max_results=5))
    
    print("\n=== 제조업체 검색: CCTV ===")
    result = search_manufacturers("CCTV")
    print(format_company_results(result, max_results=5))
