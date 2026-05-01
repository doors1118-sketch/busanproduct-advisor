"""
부산 지역업체 검색 API 클라이언트 (모니터링 시스템 챗봇 전용 연동)
"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("MONITORING_COMPANY_API_BASE_URL", "http://127.0.0.1:8000")

last_search_results: dict = {}
last_search_query: str = ""

def _sanitize_candidate(candidate: dict) -> dict:
    """민감정보 필터"""
    keys_to_remove = [
        "businessNo", "biz_no", "사업자등록번호", 
        "internal_join_key", "API key", "api_key", 
        "token", "serviceKey", "개인 휴대전화", 
        "이메일", "email"
    ]
    for k in keys_to_remove:
        candidate.pop(k, None)
    return candidate

def _normalize_response(data: dict, is_list_api: bool = False) -> dict:
    """후보 row 정규화"""
    meta = data.get("meta", {})
    candidates = data.get("candidates", [])

    
    normalized = []
    for c in candidates:
        c = _sanitize_candidate(c)
        normalized_c = {
            "company_id": c.get("company_id", "unknown"),
            "company_name": c.get("company_name", c.get("업체명", "")),
            "location": c.get("location", c.get("소재지", "")),
            "address": c.get("address", c.get("주소", "")),
            "representative_name": c.get("representative_name", c.get("대표자명", "")),
            "corporate_phone": c.get("corporate_phone", c.get("전화번호", "")),
            "license_or_business_type": c.get("license_or_business_type", []),
            "main_products": c.get("main_products", []),
            "candidate_types": c.get("candidate_types", []),
            "primary_candidate_type": c.get("primary_candidate_type", "unknown"),
            "route_codes": c.get("route_codes", []),
            "check_codes": c.get("check_codes", []),
            "business_status": c.get("business_status", "unknown"),
            "business_status_label": c.get("business_status_label", ""),
            "business_status_checked_at": c.get("business_status_checked_at", ""),
            "business_status_freshness": c.get("business_status_freshness", "unknown"),
            "display_status": "후보",
            "legal_eligibility_status": "확인 필요",
            "contract_possible_auto_promoted": False,
            "source_refs": c.get("source_refs", [])
        }
        normalized.append(normalized_c)
        
    return {
        "meta": meta,
        "candidates": normalized,
        "company_source_status": "live_company_lookup",
        "company_cache_mode": "live_only",
        "company_cache_used": False,
        "company_search_status": "success"
    }

def _api_get(endpoint: str, params: dict = None, is_list_api: bool = False) -> dict:
    """공통 GET 요청"""
    req_timeout = (1, 5) if is_list_api else (1, 3)
    req_params = params if params is not None else {}
    req_url = f"{BASE_URL}{endpoint}"
    
    try:
        resp = requests.get(req_url, params=req_params, timeout=req_timeout)
        resp.raise_for_status()
        data = resp.json()
        
        if is_list_api:
            # list API는 candidates 그대로 반환 (단순 목록)
            return {
                "meta": data.get("meta", {}),
                "candidates": data.get("candidates", []),
                "company_source_status": "live_company_lookup",
                "company_cache_mode": "live_only",
                "company_cache_used": False,
                "company_search_status": "success"
            }
        return _normalize_response(data)
            
    except Exception as e:
        print(f"  [API Error] {endpoint} failed: {e}")
        return {
            "meta": {},
            "candidates": [],
            "company_source_status": "company_cache_failed",
            "company_cache_mode": "none",
            "company_cache_used": False,
            "company_search_status": "failed",
            "error": "업체 후보 조회 실패"
        }

def search_by_license(query: str) -> dict:
    res = _api_get("/api/chatbot/company/license-search", {"license_name": query})
    global last_search_results, last_search_query
    last_search_results = res
    last_search_query = f"면허: {query}"
    return res

def search_by_product(query: str) -> dict:
    res = _api_get("/api/chatbot/company/product-search", {"product_name": query})
    global last_search_results, last_search_query
    last_search_results = res
    last_search_query = f"품목: {query}"
    return res

def search_by_category(query: str) -> dict:
    res = _api_get("/api/chatbot/company/category-search", {"category_name": query})
    global last_search_results, last_search_query
    last_search_results = res
    last_search_query = f"분류: {query}"
    return res

def search_manufacturers(query: str) -> dict:
    res = _api_get("/api/chatbot/company/manufacturers", {"product_name": query})
    global last_search_results, last_search_query
    last_search_results = res
    last_search_query = f"제조업체: {query}"
    return res

def get_license_list(limit: int = 50) -> dict:
    return _api_get("/api/chatbot/company/license-list", {"limit": limit}, is_list_api=True)

def get_product_list(limit: int = 50) -> dict:
    return _api_get("/api/chatbot/company/product-list", {"limit": limit}, is_list_api=True)

def get_category_list(limit: int = 50) -> dict:
    return _api_get("/api/chatbot/company/category-list", {"limit": limit}, is_list_api=True)

def format_company_results(data: dict, max_results: int = 10) -> str:
    """Gemini/LLM context용 텍스트 변환 (개인정보 미포함)"""
    if data.get("company_search_status") == "failed":
        return "업체 후보 조회 실패"
        
    candidates = data.get("candidates", [])
    if not candidates:
        return "검색 결과가 없습니다."
        
    total = len(candidates)
    lines = [f"부산 지역업체 검색 결과: 총 {total}건 (상위 {min(max_results, total)}건 표시)"]
    lines.append("")
    
    for i, c in enumerate(candidates[:max_results]):
        # 리스트 API 응답의 경우 dict가 아닐 수 있으나, 만약 dict라면 안전하게 get 사용
        if isinstance(c, dict) and "company_name" in c:
            name = c.get("company_name", "")
            loc = c.get("location", "")
            lic = ", ".join(c.get("license_or_business_type", []))
            prod = ", ".join(c.get("main_products", []))
            biz_status = c.get("business_status", "")
            
            line = f"{i+1}. {name}"
            if loc:
                line += f" ({loc})"
            if lic:
                line += f" -- 면허: {lic}"
            if prod:
                line += f" -- 주요품목: {prod}"
            if biz_status and biz_status not in ("unknown", "stale"):
                line += f" [{biz_status}]"
            elif biz_status in ("unknown", "stale"):
                line += f" [영업상태 확인 필요]"
                
            lines.append(line)
        else:
            # 리스트 API 문자열 결과 등
            lines.append(f"{i+1}. {c}")
            
    if total > max_results:
        lines.append(f"\n... 외 {total - max_results}건")
        
    return "\n".join(lines)

def results_to_excel(data: dict = None) -> bytes:
    import pandas as pd
    import io
    if data is None:
        data = last_search_results
    
    candidates = data.get("candidates", [])
    if not candidates:
        return b""
        
    rows = []
    for c in candidates:
        if isinstance(c, dict) and "company_name" in c:
            row = {
                "업체명": c.get("company_name", ""),
                "소재지": c.get("location", ""),
                "상세주소": c.get("address", ""),
                "대표자명": c.get("representative_name", ""),
                "법인 대표전화": c.get("corporate_phone", ""),
                "면허/업종": ", ".join(c.get("license_or_business_type", [])),
                "주요품목": ", ".join(c.get("main_products", [])),
                "영업상태": c.get("business_status", "확인 필요")
            }
            rows.append(row)
        
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf.getvalue()

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    print("=== Test Mode ===")
    
    print("1. 소방시설공사업 검색")
    r1 = search_by_license("소방시설공사업")
    print(format_company_results(r1, 3))
    print(f"meta: {r1.get('meta')}")
    print(f"company_source_status: {r1.get('company_source_status')}")
    
    print("\n2. 기초 목록 API (get_license_list)")
    rl = get_license_list()
    if rl.get("candidates"):
        print(f"목록 {len(rl.get('candidates'))}건 중 3건 샘플:")
        print(rl.get('candidates')[:3])
    else:
        print(rl.get("error", "No data"))
