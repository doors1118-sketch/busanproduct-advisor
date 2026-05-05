"""
지방계약법 시행령에서 수의계약 관련 조문 + 금액 기준 찾기
"""
import requests
import xml.etree.ElementTree as ET
import re
import os

BASE_URL = "http://www.law.go.kr/DRF"
OC = "busanproduct1"
OUT = os.path.join(os.path.dirname(__file__), "article_threshold_search.txt")

def api_get(endpoint, params, timeout=15):
    params["OC"] = OC
    params["type"] = "XML"
    r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=timeout)
    r.raise_for_status()
    return ET.fromstring(r.content)

lines = []
def log(msg):
    lines.append(msg)

# ── 지방계약법 시행령 ──
log("=" * 60)
log("지방계약법 시행령 — 수의계약/금액 관련 조문 검색")
log("=" * 60)

root = api_get("lawService.do", {"target": "law", "MST": "281055"})

keywords = ["수의계약", "수의", "소액", "금액", "추정가격", "2천만원", "5천만원", "2천", "5천",
            "별표", "행정안전부장관", "공동도급", "공동계약", "100분의"]

for jo in root.findall(".//조문단위"):
    jo_no_el = jo.find("조문번호")
    jo_title_el = jo.find("조문제목")
    jo_content_el = jo.find("조문내용")
    
    jo_no = jo_no_el.text if jo_no_el is not None else ""
    jo_title = jo_title_el.text if jo_title_el is not None else ""
    jo_content = jo_content_el.text if jo_content_el is not None else ""
    
    # 항 내용 합치기
    all_text = jo_content
    hang_texts = []
    for hang in jo.findall(".//항"):
        hang_el = hang.find("항내용")
        if hang_el is not None and hang_el.text:
            hang_texts.append(hang_el.text)
            all_text += " " + hang_el.text
    
    # 호 내용도 합치기
    for ho in jo.findall(".//호"):
        ho_el = ho.find("호내용")
        if ho_el is not None and ho_el.text:
            all_text += " " + ho_el.text
    
    # 키워드 매치
    matched = [kw for kw in keywords if kw in all_text]
    if matched:
        log(f"\n{'─'*50}")
        log(f"[조문번호 {jo_no}] {jo_title}")
        log(f"  매치 키워드: {matched}")
        log(f"  본문: {jo_content[:300]}")
        for i, ht in enumerate(hang_texts):
            log(f"  [항{i+1}] {ht[:400]}")
        
        # 금액 패턴 추출
        amounts = re.findall(r'(\d[\d,]*)\s*만\s*원', all_text)
        if amounts:
            log(f"  → 금액(만원): {amounts}")
        amounts2 = re.findall(r'(\d[\d,]*)\s*억', all_text)
        if amounts2:
            log(f"  → 금액(억): {amounts2}")
        pct = re.findall(r'(\d+)\s*분의\s*(\d+)', all_text)
        if pct:
            log(f"  → 비율: {[f'{a}분의{b}' for a,b in pct]}")

# ── 국가계약법 시행령 ──
log(f"\n\n{'='*60}")
log("국가계약법 시행령 — 수의계약/공동도급 관련 조문 검색")
log("=" * 60)

root2 = api_get("lawService.do", {"target": "law", "MST": "280803"})

for jo in root2.findall(".//조문단위"):
    jo_no_el = jo.find("조문번호")
    jo_title_el = jo.find("조문제목")
    jo_content_el = jo.find("조문내용")
    
    jo_no = jo_no_el.text if jo_no_el is not None else ""
    jo_title = jo_title_el.text if jo_title_el is not None else ""
    jo_content = jo_content_el.text if jo_content_el is not None else ""
    
    all_text = jo_content
    hang_texts = []
    for hang in jo.findall(".//항"):
        hang_el = hang.find("항내용")
        if hang_el is not None and hang_el.text:
            hang_texts.append(hang_el.text)
            all_text += " " + hang_el.text
    
    for ho in jo.findall(".//호"):
        ho_el = ho.find("호내용")
        if ho_el is not None and ho_el.text:
            all_text += " " + ho_el.text
    
    matched = [kw for kw in keywords if kw in all_text]
    if matched:
        log(f"\n{'─'*50}")
        log(f"[조문번호 {jo_no}] {jo_title}")
        log(f"  매치 키워드: {matched}")
        log(f"  본문: {jo_content[:300]}")
        for i, ht in enumerate(hang_texts):
            log(f"  [항{i+1}] {ht[:400]}")
        
        amounts = re.findall(r'(\d[\d,]*)\s*만\s*원', all_text)
        if amounts:
            log(f"  → 금액(만원): {amounts}")
        pct = re.findall(r'(\d+)\s*분의\s*(\d+)', all_text)
        if pct:
            log(f"  → 비율: {[f'{a}분의{b}' for a,b in pct]}")

with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"[SAVED] {OUT}")
print(f"관련 조문 총 {len([l for l in lines if l.startswith('[조문번호')])}개")
