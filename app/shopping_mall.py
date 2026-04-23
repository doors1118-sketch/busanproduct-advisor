"""
나라장터 종합쇼핑몰 품목 검색 API 클라이언트
- MAS(다수공급자계약) 품목을 품목명으로 검색
- 부산 소재 업체 자동 필터링 (hdoffceLocplc 기준)
- 종합쇼핑몰 등록 상품은 별도 계약 없이 즉시 구매 가능
"""
import requests
import io

API_KEY = "c551b235466f84865b201c21869bc5b08cdf0633cdb4a3105dfb1e19c6427865"
BASE_URL = "https://apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService"
TIMEOUT = 20

# 최근 검색 결과 저장 (UI 다운로드용)
last_mall_results: dict = {}
last_mall_query: str = ""


def search_mall_products(product_name: str, busan_only: bool = True,
                         num_results: int = 100) -> dict:
    """
    품목명으로 종합쇼핑몰 MAS 등록 상품 검색.
    busan_only=True이면 부산 소재 업체만 필터링.
    """
    try:
        r = requests.get(
            f"{BASE_URL}/getMASCntrctPrdctInfoList",
            params={
                "serviceKey": API_KEY,
                "numOfRows": str(num_results),
                "pageNo": "1",
                "type": "json",
                "prdctClsfcNoNm": product_name,
            },
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        body = data.get("response", {}).get("body", {})
        items = body.get("items", [])
        total = body.get("totalCount", 0)

        if busan_only and items:
            items = [
                item for item in items
                if "부산" in str(item.get("hdoffceLocplc", ""))
                or "부산" in str(item.get("fctryLocplc", ""))
            ]

        return {
            "totalCount": total,
            "filteredCount": len(items),
            "items": items,
        }
    except Exception as e:
        return {"totalCount": 0, "filteredCount": 0, "items": [], "error": str(e)}


def format_mall_results(data: dict, max_results: int = 5) -> str:
    """종합쇼핑몰 검색 결과를 Gemini 보조자료 텍스트로 변환"""
    items = data.get("items", [])
    total = data.get("totalCount", 0)
    filtered = data.get("filteredCount", len(items))

    if not items:
        return ""

    lines = [f"[나라장터 종합쇼핑몰] 전국 {total}건 중 부산 업체 {filtered}건"]

    for i, item in enumerate(items[:max_results]):
        company = item.get("cntrctCorpNm", "")
        spec = item.get("prdctSpecNm", "")
        price = item.get("cntrctPrceAmt", "")
        method = item.get("cntrctMthdNm", "")
        location = item.get("hdoffceLocplc", "")
        excellent = item.get("exclncPrcrmntPrdctYn", "N") == "Y"
        sme = item.get("smetprCmptProdctYn", "N") == "Y"
        cert = item.get("qltyRltnCertInfo", "")
        end_date = item.get("cntrctEndDate", "")

        price_str = f"{int(price):,}원" if price else "가격 미정"
        tags = []
        if excellent:
            tags.append("우수조달")
        if sme:
            tags.append("중기간경쟁")
        tag_str = f" ({', '.join(tags)})" if tags else ""

        line = f"{i+1}. {spec}"
        line += f"\n   업체: {company} ({location})"
        line += f" | 가격: {price_str}{tag_str}"
        if cert:
            line += f"\n   인증: {cert}"
        if end_date:
            line += f" | 계약종료: {end_date}"
        lines.append(line)

    lines.append("\n* 종합쇼핑몰 등록 상품은 별도 계약 없이 나라장터에서 바로 구매 가능")
    return "\n".join(lines)


def results_to_excel(data: dict = None) -> bytes:
    """종합쇼핑몰 검색 결과를 Excel 바이트로 변환"""
    import pandas as pd

    if data is None:
        data = last_mall_results

    items = data.get("items", [])
    if not items:
        return b""

    fields = {
        "cntrctCorpNm": "업체명",
        "hdoffceLocplc": "본사소재지",
        "prdctSpecNm": "물품규격",
        "cntrctPrceAmt": "계약가격",
        "prdctUnit": "단위",
        "cntrctMthdNm": "계약방법",
        "exclncPrcrmntPrdctYn": "우수조달",
        "smetprCmptProdctYn": "중기간경쟁",
        "qltyRltnCertInfo": "인증정보",
        "cntrctBgnDate": "계약시작",
        "cntrctEndDate": "계약종료",
        "prdctClsfcNoNm": "품명",
    }

    rows = []
    for item in items:
        row = {kor: item.get(eng, "") for eng, kor in fields.items()}
        rows.append(row)

    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    return buf.getvalue()


# ─────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')

    print("=== LED (부산 업체만) ===")
    r = search_mall_products("LED", busan_only=True)
    print(format_mall_results(r, max_results=5))
