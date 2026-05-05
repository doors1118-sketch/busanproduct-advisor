"""
별표 내용 추출 (인코딩 안전)
"""
import requests
import xml.etree.ElementTree as ET
import re
import os

BASE_URL = "http://www.law.go.kr/DRF"
OC = "busanproduct1"
OUT = os.path.join(os.path.dirname(__file__), "annex_extract_result.txt")

def api_get(endpoint, params, timeout=15):
    params["OC"] = OC
    params["type"] = "XML"
    r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=timeout)
    r.raise_for_status()
    return ET.fromstring(r.content)

lines = []

def log(msg):
    lines.append(msg)
    print(msg)

# ── 1. 지방계약법 시행령 별표 ──
log("=" * 60)
log("1. 지방계약법 시행령 (MST: 281055)")
log("=" * 60)

root = api_get("lawService.do", {"target": "law", "MST": "281055"})

# 별표 추출
for annex in root.findall(".//별표단위"):
    title = ""
    content = ""
    hwp_link = ""
    for child in annex:
        if child.tag == "별표제목":
            title = child.text or ""
        elif child.tag == "별표내용":
            content = child.text or ""
        elif child.tag == "별표파일링크":
            hwp_link = child.text or ""
        elif "HWP" in child.tag:
            log(f"  HWP 관련: <{child.tag}> = {child.text or ''}")
        elif "PDF" in child.tag:
            log(f"  PDF 관련: <{child.tag}> = {child.text or ''}")
    
    log(f"\n[별표 제목] {title}")
    log(f"[별표 내용 길이] {len(content)} 자")
    log(f"[HWP 링크] {hwp_link}")
    
    if content:
        log(f"\n[별표 내용 전문]")
        log(content[:3000])
    
    # 금액 추출 시도
    log(f"\n[금액 패턴 추출]")
    # 한국 금액 패턴: 숫자+만원, 숫자+억원, 숫자+천만원 등
    amount_patterns = [
        r'(\d[\d,]*)\s*만\s*원',
        r'(\d[\d,]*)\s*억\s*원',
        r'(\d[\d,]*)\s*천만\s*원',
        r'(\d[\d,]*)\s*백만\s*원',
        r'(\d[\d,]*)\s*원',
    ]
    for pat in amount_patterns:
        matches = re.findall(pat, content)
        if matches:
            log(f"  패턴 '{pat}': {matches[:10]}")

# 조문 제25조 확인 (수의계약)
log(f"\n{'='*60}")
log("제25조 (수의계약 대상) 조문 확인")
log("=" * 60)

for jo in root.findall(".//조문단위"):
    jo_no = jo.find("조문번호")
    if jo_no is not None and jo_no.text and "0025" in jo_no.text:
        title = jo.find("조문제목")
        content = jo.find("조문내용")
        log(f"조문번호: {jo_no.text}")
        log(f"제목: {title.text if title is not None else ''}")
        log(f"내용: {content.text if content is not None else ''}")
        for hang in jo.findall(".//항"):
            hang_content = hang.find("항내용")
            if hang_content is not None and hang_content.text:
                log(f"  [항] {hang_content.text[:500]}")

# ── 2. 국가계약법 시행령 - 제26조 (수의계약) ──
log(f"\n{'='*60}")
log("2. 국가계약법 시행령 (MST: 280803)")
log("=" * 60)

root2 = api_get("lawService.do", {"target": "law", "MST": "280803"})

for jo in root2.findall(".//조문단위"):
    jo_no = jo.find("조문번호")
    if jo_no is not None and jo_no.text and ("0026" in jo_no.text or "0072" in jo_no.text):
        title = jo.find("조문제목")
        content = jo.find("조문내용")
        log(f"\n조문번호: {jo_no.text}")
        log(f"제목: {title.text if title is not None else ''}")
        log(f"내용: {(content.text if content is not None else '')[:500]}")
        for hang in jo.findall(".//항"):
            hang_content = hang.find("항내용")
            if hang_content is not None and hang_content.text:
                if "공동" in hang_content.text or "수의" in hang_content.text or "금액" in hang_content.text or "별표" in hang_content.text:
                    log(f"  [관련항] {hang_content.text[:500]}")

# 저장
with open(OUT, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))
print(f"\n[SAVED] {OUT}")
