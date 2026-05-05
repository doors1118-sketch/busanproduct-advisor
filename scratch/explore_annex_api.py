"""
Phase 1 탐색: 법제처 API로 별표 XML 구조 확인

지방계약법 시행령 별표 1 = 소액수의계약 기준금액 (핵심 타겟)
"""
import requests
import xml.etree.ElementTree as ET
import json
import os

BASE_URL = "http://www.law.go.kr/DRF"
OC = "busanproduct1"

def api_get(endpoint, params, timeout=15):
    params["OC"] = OC
    params["type"] = "XML"
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=timeout)
        r.raise_for_status()
        return r.content, ET.fromstring(r.content)
    except Exception as e:
        print(f"[ERROR] {e}")
        return None, None

# ── 지방계약법 시행령 (MST: 281055) ──
print("=" * 60)
print("1. 지방계약법 시행령 (MST: 281055) - 별표 조회")
print("=" * 60)

raw, root = api_get("lawService.do", {"target": "law", "MST": "281055"})
if root is not None:
    # 법령명 확인
    name_el = root.find(".//법령명_한글")
    if name_el is None:
        name_el = root.find(".//법령명한글")
    print(f"법령명: {name_el.text if name_el is not None else 'N/A'}")
    
    # 별표 구조 탐색
    annexes = root.findall(".//별표단위")
    print(f"별표 수: {len(annexes)}")
    
    for i, annex in enumerate(annexes):
        print(f"\n--- 별표 {i+1} ---")
        for child in annex:
            text = (child.text or "")[:200]
            print(f"  <{child.tag}>: {text}")
    
    # 별표가 없으면 다른 경로 탐색
    if not annexes:
        print("\n별표단위 태그 없음. 다른 경로 탐색:")
        for tag in ["별표", "별표서식", "별첨"]:
            found = root.findall(f".//{tag}")
            if found:
                print(f"  <{tag}> 발견: {len(found)}개")
                for f_el in found[:3]:
                    for child in f_el:
                        print(f"    <{child.tag}>: {(child.text or '')[:100]}")

    # 전체 XML 태그 구조 요약
    print("\n--- XML 최상위 태그 구조 ---")
    tags = set()
    for el in root.iter():
        tags.add(el.tag)
    for t in sorted(tags):
        print(f"  {t}")

# raw XML의 별표 관련 부분 저장 (디버깅용)
if raw:
    out_path = os.path.join(os.path.dirname(__file__), "annex_raw_debug.xml")
    # 별표 관련 부분만 추출
    text = raw.decode("utf-8", errors="replace")
    # 별표 키워드 주변 텍스트 추출
    import re
    matches = list(re.finditer(r"별표|別表", text))
    if matches:
        print(f"\n'별표' 키워드 {len(matches)}건 발견")
        for m in matches[:5]:
            start = max(0, m.start() - 50)
            end = min(len(text), m.end() + 300)
            print(f"  ...{text[start:end]}...")
    else:
        print("\n'별표' 키워드 없음")

print("\n" + "=" * 60)
print("2. 국가계약법 시행령 (MST: 280803) - 공동도급 관련")
print("=" * 60)

raw2, root2 = api_get("lawService.do", {"target": "law", "MST": "280803"})
if root2 is not None:
    name_el = root2.find(".//법령명_한글") or root2.find(".//법령명한글")
    print(f"법령명: {name_el.text if name_el is not None else 'N/A'}")
    
    annexes2 = root2.findall(".//별표단위")
    print(f"별표 수: {len(annexes2)}")
    for i, annex in enumerate(annexes2[:5]):
        print(f"\n--- 별표 {i+1} ---")
        for child in annex:
            text = (child.text or "")[:200]
            print(f"  <{child.tag}>: {text}")

# ── 수의계약 관련 조문 확인 ──
print("\n" + "=" * 60)
print("3. 지방계약법 시행령 제25조 (수의계약 대상) 조문 확인")
print("=" * 60)

if root is not None:
    for jo in root.findall(".//조문단위"):
        jo_no = jo.find("조문번호")
        if jo_no is not None and jo_no.text and "0025" in jo_no.text:
            print(f"조문번호: {jo_no.text}")
            title = jo.find("조문제목")
            content = jo.find("조문내용")
            print(f"제목: {title.text if title is not None else ''}")
            print(f"내용: {(content.text if content is not None else '')[:500]}")
            # 항 확인
            for hang in jo.findall(".//항"):
                hang_content = hang.find("항내용")
                if hang_content is not None and hang_content.text:
                    if "별표" in hang_content.text or "금액" in hang_content.text:
                        print(f"  [관련항] {hang_content.text[:300]}")
