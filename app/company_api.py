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
import time

BASE_URL = "https://busanproduct.co.kr"
TIMEOUT = 10

# 국세청 사업자등록 상태조회 API
NTS_STATUS_URL = "https://api.odcloud.kr/api/nts-businessman/v1/status"
NTS_SERVICE_KEY = "c551b235466f84865b201c21869bc5b08cdf0633cdb4a3105dfb1e19c6427865"

# 최근 검색 결과 저장 (챗봇 UI에서 전체 목록 다운로드용)
last_search_results: dict = {}
last_search_query: str = ""

# 국세청 상태 캐시: {사업자번호: {status: {...}, ts: timestamp}}
_nts_cache: dict = {}
_NTS_CACHE_TTL = 86400  # 24시간 (초)


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


# ─────────────────────────────────────────────
# 국세청 사업자등록 상태조회 (휴폐업 확인)
# ─────────────────────────────────────────────
def verify_business_status(biz_numbers: list[str]) -> dict:
    """
    국세청 API로 사업자등록번호 상태 배치 조회 (최대 100건).
    24시간 TTL 캐시 적용 — 캐시 히트 건은 API 호출 생략.
    Returns: {사업자번호: {b_stt: '계속사업자', b_stt_cd: '01', ...}}
    """
    if not biz_numbers:
        return {}

    # 하이픈 제거 + 10자리 필터
    clean_numbers = [n.replace("-", "").strip() for n in biz_numbers]
    clean_numbers = [n for n in clean_numbers if len(n) == 10 and n.isdigit()]

    if not clean_numbers:
        return {}

    now = time.time()
    results = {}
    to_query = []  # 캐시 미스 — API 조회 필요

    # 캐시 히트 확인
    for bno in clean_numbers:
        cached = _nts_cache.get(bno)
        if cached and (now - cached["ts"]) < _NTS_CACHE_TTL:
            results[bno] = cached["status"]  # 캐시 히트
        else:
            to_query.append(bno)  # 캐시 미스

    if not to_query:
        return results  # 전부 캐시 히트

    # 100건씩 배치 처리 (캐시 미스 건만)
    for i in range(0, len(to_query), 100):
        batch = to_query[i:i + 100]
        try:
            resp = requests.post(
                NTS_STATUS_URL,
                params={"serviceKey": NTS_SERVICE_KEY},
                json={"b_no": batch},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            for item in data.get("data", []):
                bno = item.get("b_no", "")
                status = {
                    "b_stt": item.get("b_stt", ""),
                    "b_stt_cd": item.get("b_stt_cd", ""),
                    "tax_type": item.get("tax_type", ""),
                    "end_dt": item.get("end_dt", ""),
                }
                results[bno] = status
                _nts_cache[bno] = {"status": status, "ts": now}  # 캐시 저장
        except Exception as e:
            print(f"  [NTS] status check failed: {e}")

    return results


def filter_active_companies(data: dict) -> dict:
    """
    검색 결과에서 계속사업자(01)만 남기고 휴폐업 업체 제외.
    국세청 API 실패 시 원본 데이터 그대로 반환 (Fail-open).
    """
    companies = data.get("업체목록", [])
    if not companies:
        return data

    # 사업자번호 추출
    biz_numbers = [c.get("사업자번호", "") for c in companies if c.get("사업자번호")]
    if not biz_numbers:
        return data  # 사업자번호 없으면 필터링 불가

    # 국세청 상태 조회
    statuses = verify_business_status(biz_numbers)
    if not statuses:
        return data  # API 실패 시 원본 반환

    # 계속사업자(01)만 필터링 + 상태 미확인 업체도 포함
    filtered = []
    excluded_count = 0
    for c in companies:
        bno = c.get("사업자번호", "").replace("-", "").strip()
        status = statuses.get(bno)
        if status and status["b_stt_cd"] in ("02", "03"):
            excluded_count += 1
            continue  # 휴업(02) 또는 폐업(03) 제외
        c["_사업자상태"] = status["b_stt"] if status else "미확인"
        filtered.append(c)

    if excluded_count > 0:
        print(f"  [NTS] {excluded_count} companies excluded (closed/suspended)")

    return {
        **data,
        "업체목록": filtered,
        "검색결과수": len(filtered),
        "_제외업체수": excluded_count,
    }


def _search_and_enrich(endpoint: str, query: str) -> dict:
    """busanproduct 검색 → 휴폐업 필터 → 정책기업 태깅"""
    from policy_companies import enrich_company_results
    data = filter_active_companies(_api_get(endpoint, {"q": query}))
    return enrich_company_results(data)


def search_by_license(query: str) -> dict:
    """면허(업종)으로 업체 검색. 예: '전기공사', '소방'"""
    return _search_and_enrich("/api/company/license-search", query)


def search_by_product(query: str) -> dict:
    """대표품목으로 업체 검색. 예: 'LED조명', 'CCTV'"""
    return _search_and_enrich("/api/company/product-search", query)


def search_by_category(query: str) -> dict:
    """분류코드(UNSPSC) 또는 분류명으로 업체 검색. 예: '43', '소방설비'"""
    return _search_and_enrich("/api/company/category-search", query)


def search_manufacturers(query: str) -> dict:
    """제조업체 검색. 예: 'LED'"""
    return _search_and_enrich("/api/company/manufacturers", query)


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
            line += f" -- {product}"
        if biz_type:
            line += f" [{biz_type}]"
        if mfg:
            line += f" ({mfg})"
        # 정책기업 태그 표시
        policy_tags = c.get("_정책기업", [])
        if policy_tags:
            line += f" <{', '.join(policy_tags)}>"
        # 사업자 상태 표시
        biz_status = c.get("_사업자상태", "")
        if biz_status:
            line += f" [{biz_status}]"
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
