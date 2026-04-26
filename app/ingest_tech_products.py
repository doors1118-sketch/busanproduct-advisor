"""
중기부 기술개발제품 인증현황 API → 부산 업체 필터 → JSON 캐시
- 성능인증/기술개발 제품: 시행령 제25조 제1항 제6호 라목 (수의계약)
- 사업자번호로 busanproduct 지역업체DB 매칭
- 만료일자 기반 유효 제품만 필터링
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
import os
import json
import requests
from datetime import datetime

API_KEY = "c551b235466f84865b201c21869bc5b08cdf0633cdb4a3105dfb1e19c6427865"
# 최신 버전 (20250512): 사업자등록번호, 만료일자 포함
API_URL = "https://api.odcloud.kr/api/3033913/v1/uddi:834e8428-51b3-420b-9fd4-aaee942e4916"

CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tech_products.json")
BUSAN_BIZ_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policy_companies.json")


def _load_busan_biz_numbers() -> set:
    """busanproduct DB + 정책기업 DB에서 부산 사업자번호 수집"""
    biz_set = set()

    # 1) policy_companies.json (이미 부산 업체)
    if os.path.exists(BUSAN_BIZ_PATH):
        with open(BUSAN_BIZ_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            biz_set.update(data.keys())

    # 2) busanproduct API 샘플링
    try:
        import requests as req
        for q in ["가","나","다","라","마","바","사","아","자","차","카","타","파","하","LED","CCTV","IT"]:
            r = req.get("https://busanproduct.co.kr/api/company/product-search",
                       params={"q": q}, timeout=10)
            for c in r.json().get("업체목록", []):
                bno = str(c.get("사업자번호", "")).replace("-", "").strip()
                if len(bno) == 10:
                    biz_set.add(bno)
    except Exception:
        pass

    return biz_set


def fetch_all_tech_products() -> list:
    """API에서 전체 기술개발제품 조회"""
    all_items = []
    page = 1
    while True:
        r = requests.get(API_URL, params={
            "serviceKey": API_KEY,
            "page": page,
            "perPage": 500,
        }, timeout=15)
        data = r.json()
        items = data.get("data", [])
        if not items:
            break
        all_items.extend(items)
        total = data.get("totalCount", 0)
        print(f"  page {page}: {len(items)} items (total: {total})")
        if len(all_items) >= total:
            break
        page += 1
    return all_items


def build_tech_products_db():
    """API → 부산 필터 → 유효기간 체크 → JSON 캐시 저장"""
    print("=" * 50)
    print("  Tech Product Certification DB Build")
    print("=" * 50)

    # 1. API 전체 조회
    print("\n[1] Fetching all tech products from API...")
    all_items = fetch_all_tech_products()
    print(f"  Total: {len(all_items)}")

    # 2. 부산 사업자번호 로드
    print("\n[2] Loading Busan business numbers...")
    busan_biz = _load_busan_biz_numbers()
    print(f"  Busan biz numbers: {len(busan_biz)}")

    # 3. 부산 업체 필터 + 만료 체크
    today = datetime.now().strftime("%Y%m%d")
    busan_products = []
    expired_count = 0

    for item in all_items:
        bno = str(item.get("사업자등록번호", "")).replace("-", "").strip()
        if len(bno) == 9:
            bno = "0" + bno
        if len(bno) != 10:
            continue

        # 부산 업체인지 확인
        if bno not in busan_biz:
            continue

        # 만료일 체크
        expire = str(item.get("만료일자", "")).replace("-", "").replace(".", "").strip()[:8]
        if expire and expire < today:
            expired_count += 1
            continue

        busan_products.append({
            "biz_no": bno,
            "company": str(item.get("업체명", "")),
            "representative": str(item.get("대표자", "")),
            "cert_type": str(item.get("인증구분", "")),
            "cert_no": str(item.get("인증번호", "")),
            "product_name": str(item.get("인증제품명", "")),
            "cert_date": str(item.get("인증일자", "")),
            "expire_date": str(item.get("만료일자", "")),
        })

    print(f"\n[3] Busan tech products: {len(busan_products)} (expired: {expired_count})")

    # 4. JSON 저장
    result = {
        "updated": datetime.now().isoformat(),
        "total_api": len(all_items),
        "busan_valid": len(busan_products),
        "busan_expired": expired_count,
        "products": busan_products,
    }

    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {CACHE_PATH}")

    # 통계
    cert_types = {}
    for p in busan_products:
        ct = p["cert_type"]
        cert_types[ct] = cert_types.get(ct, 0) + 1
    print(f"\n  Certification type distribution:")
    for ct, cnt in sorted(cert_types.items(), key=lambda x: -x[1]):
        print(f"    {ct}: {cnt}")

    return result


# ─────────────────────────────────────────
# 검색 함수 (챗봇에서 호출)
# ─────────────────────────────────────────
_tech_db = None

def _load_db():
    global _tech_db
    if _tech_db is not None:
        return _tech_db
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            _tech_db = json.load(f)
    else:
        _tech_db = {"products": []}
    return _tech_db


def search_tech_products(query: str, max_results: int = 5) -> str:
    """키워드로 부산 기술개발제품 검색"""
    db = _load_db()
    products = db.get("products", [])
    if not products:
        return ""

    query_lower = query.lower()
    matches = [
        p for p in products
        if query_lower in p.get("product_name", "").lower()
        or query_lower in p.get("cert_type", "").lower()
        or query_lower in p.get("company", "").lower()
    ]

    if not matches:
        return ""

    lines = [f"[기술개발제품 인증 현황] 부산 업체 {len(matches)}건"]
    for p in matches[:max_results]:
        line = f"- {p['product_name']}"
        line += f"\n  업체: {p['company']} | 인증: {p['cert_type']} ({p['cert_no']})"
        line += f"\n  인증일: {p['cert_date']} | 만료: {p['expire_date']}"
        lines.append(line)

    lines.append("\n* 기술개발제품 인증은 우선구매 또는 수의계약 검토의 후보 정보입니다. 인증 유효기간, 제품 적합성 확인이 필요합니다.")
    return "\n".join(lines)


def get_tech_products_by_biz_no(biz_no: str) -> list:
    """사업자번호로 기술개발제품 인증 조회"""
    db = _load_db()
    bno = str(biz_no).replace("-", "").strip()
    return [p for p in db.get("products", []) if p.get("biz_no") == bno]


if __name__ == "__main__":
    build_tech_products_db()
