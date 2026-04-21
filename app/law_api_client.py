"""
법제처 Open API 클라이언트
https://open.law.go.kr

법령 검색, 조문 조회, 해석례·판례 검색 기능 제공.
"""
import os
import requests
import xml.etree.ElementTree as ET
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://www.law.go.kr/DRF"
OC = os.getenv("LAW_API_OC", "busanproduct")


def _request(endpoint: str, params: dict) -> Optional[ET.Element]:
    """법제처 API 공통 요청 함수. XML 응답을 파싱하여 반환."""
    params.setdefault("OC", OC)
    params.setdefault("type", "XML")
    try:
        resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=10)
        resp.raise_for_status()
        return ET.fromstring(resp.content)
    except Exception as e:
        print(f"[법제처 API 오류] {e}")
        return None


# ─────────────────────────────────────────────
# 1. 법령 검색
# ─────────────────────────────────────────────

def search_law(query: str, display: int = 5) -> list[dict]:
    """
    법령명으로 검색하여 목록 반환.

    Args:
        query: 검색어 (예: "지방계약법")
        display: 결과 개수 (기본 5)

    Returns:
        [{"법령ID": ..., "법령명한글": ..., "시행일자": ..., "법령MST": ...}, ...]
    """
    root = _request("lawSearch.do", {
        "target": "law",
        "query": query,
        "display": display,
    })
    if root is None:
        return []

    results = []
    for item in root.findall(".//law") or root.findall(".//LawSearch"):
        entry = {}
        for child in item:
            entry[child.tag] = child.text
        if entry:
            results.append(entry)
    return results


def get_law_text(mst: str, article_no: Optional[str] = None) -> dict:
    """
    법령 MST로 조문 전체 또는 특정 조문 조회.

    Args:
        mst: 법령 MST 식별자
        article_no: 조문번호 (예: "제25조" → "002500")
                    None이면 전체 조문 반환

    Returns:
        {"법령명": ..., "조문목록": [{"조문번호": ..., "조문내용": ...}, ...]}
    """
    params = {"target": "law", "MST": mst}
    if article_no:
        params["JO"] = _normalize_article_no(article_no)

    root = _request("lawService.do", params)
    if root is None:
        return {"법령명": "", "조문목록": []}

    law_name = _find_text(root, ".//법령명_한글") or _find_text(root, ".//법령명한글") or ""

    articles = []
    for jo in root.findall(".//조문단위"):
        article = {
            "조문번호": _find_text(jo, "조문번호") or "",
            "조문여백": _find_text(jo, "조문여백") or "",
            "조문제목": _find_text(jo, "조문제목") or "",
            "조문내용": _find_text(jo, "조문내용") or "",
        }
        # 항 목록
        항목 = []
        for hang in jo.findall(".//항"):
            항_내용 = _find_text(hang, "항내용") or ""
            호목 = []
            for ho in hang.findall(".//호"):
                호_내용 = _find_text(ho, "호내용") or ""
                호목.append(호_내용)
            항목.append({"항내용": 항_내용, "호목록": 호목})
        article["항목록"] = 항목
        articles.append(article)

    return {"법령명": law_name, "조문목록": articles}


# ─────────────────────────────────────────────
# 2. 해석례·질의회신 검색
# ─────────────────────────────────────────────

def search_interpretations(query: str, display: int = 5) -> list[dict]:
    """
    해석례·질의회신 검색.

    Args:
        query: 검색어 (예: "물품 수의계약 한도")
        display: 결과 개수

    Returns:
        [{"사건명": ..., "사건번호": ..., "요지": ...}, ...]
    """
    root = _request("lawSearch.do", {
        "target": "expc",
        "query": query,
        "display": display,
    })
    if root is None:
        return []

    results = []
    for item in root.findall(".//*"):
        if item.tag in ("totalCnt", "resultCnt", "resultCode", "resultMsg"):
            continue
        entry = {}
        for child in item:
            entry[child.tag] = child.text
        if entry:
            results.append(entry)
    return results


# ─────────────────────────────────────────────
# 3. 판례 검색
# ─────────────────────────────────────────────

def search_decisions(query: str, display: int = 5) -> list[dict]:
    """
    판례 검색.

    Args:
        query: 검색어 (예: "지역제한 입찰")
        display: 결과 개수

    Returns:
        [{"사건명": ..., "사건번호": ..., "판시사항": ..., "판결요지": ...}, ...]
    """
    root = _request("lawSearch.do", {
        "target": "prec",
        "query": query,
        "display": display,
    })
    if root is None:
        return []

    results = []
    for item in root.findall(".//*"):
        if item.tag in ("totalCnt", "resultCnt", "resultCode", "resultMsg"):
            continue
        entry = {}
        for child in item:
            entry[child.tag] = child.text
        if entry:
            results.append(entry)
    return results


# ─────────────────────────────────────────────
# 유틸 함수
# ─────────────────────────────────────────────

def _normalize_article_no(article_str: str) -> str:
    """
    '제25조' → '002500', '제13조의2' → '001302' 변환.
    이미 숫자 형태면 그대로 반환.
    """
    import re
    if article_str.isdigit():
        return article_str

    match = re.match(r"제?(\d+)조(?:의(\d+))?", article_str)
    if match:
        main_no = int(match.group(1))
        sub_no = int(match.group(2)) if match.group(2) else 0
        return f"{main_no:04d}{sub_no:02d}"
    return article_str


def _find_text(root: ET.Element, xpath: str) -> Optional[str]:
    """XML 요소에서 텍스트 추출. 없으면 None 반환."""
    elem = root.find(xpath)
    return elem.text if elem is not None and elem.text else None


def format_law_for_llm(law_data: dict) -> str:
    """법령 조문 데이터를 LLM에 전달하기 좋은 텍스트로 변환."""
    lines = [f"【{law_data['법령명']}】\n"]
    for article in law_data.get("조문목록", []):
        title = article.get("조문제목", "")
        content = article.get("조문내용", "")
        lines.append(f"■ {article.get('조문번호', '')} {title}")
        lines.append(f"  {content}")
        for hang in article.get("항목록", []):
            lines.append(f"  {hang.get('항내용', '')}")
            for ho in hang.get("호목록", []):
                lines.append(f"    {ho}")
        lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# 테스트 실행
# ─────────────────────────────────────────────
if __name__ == "__main__":
    print("=== 법령 검색 테스트 ===")
    results = search_law("지방계약법")
    for r in results:
        name = r.get("법령명한글", r.get("법령명_한글", "알수없음"))
        print(f"  - {name}")

    print("\n=== 해석례 검색 테스트 ===")
    interps = search_interpretations("수의계약")
    for i in interps[:3]:
        print(f"  - {i}")
