"""
법제처 API 직접 호출 — 13종 핵심 법령 전체 조문 수집
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MCP를 거치지 않고 법제처 공공데이터 API를 직접 호출하여
Rate Limit(429) 문제 없이 전체 조문을 수집합니다.

API: http://www.law.go.kr/DRF/lawService.do
인증키: busanproduct1
"""
import os
import re
import json
import time
import sys
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    print("pip install requests 필요")
    sys.exit(1)

_ROOT = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(_ROOT, "data", "law_articles_db.json")

OC = "busanproduct1"
BASE_URL = "http://www.law.go.kr/DRF/lawService.do"

# 수집 대상
LAW_LIST = [
    {"mst": "253973", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률", "short": "지방계약법"},
    {"mst": "281055", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령", "short": "지방계약법 시행령"},
    {"mst": "282729", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행규칙", "short": "지방계약법 시행규칙"},
    {"mst": "277151", "name": "국가를 당사자로 하는 계약에 관한 법률", "short": "국가계약법"},
    {"mst": "280803", "name": "국가를 당사자로 하는 계약에 관한 법률 시행령", "short": "국가계약법 시행령"},
    {"mst": "282607", "name": "국가를 당사자로 하는 계약에 관한 법률 시행규칙", "short": "국가계약법 시행규칙"},
    {"mst": "277129", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률", "short": "중소기업구매촉진법"},
    {"mst": "281341", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령", "short": "중소기업구매촉진법 시행령"},
    {"mst": "253373", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행규칙", "short": "중소기업구매촉진법 시행규칙"},
    {"mst": "277155", "name": "조달사업에 관한 법률", "short": "조달사업법"},
    {"mst": "280891", "name": "조달사업에 관한 법률 시행령", "short": "조달사업법 시행령"},
    {"mst": "282675", "name": "조달사업에 관한 법률 시행규칙", "short": "조달사업법 시행규칙"},
    {"mst": "285569", "name": "공기업ㆍ준정부기관 계약사무규칙", "short": "공기업계약사무규칙"},
]


def _get_xml(params: dict) -> ET.Element:
    """법제처 API XML 응답 파싱."""
    params["OC"] = OC
    params["type"] = "XML"
    resp = requests.get(BASE_URL, params=params, timeout=30)
    resp.raise_for_status()
    return ET.fromstring(resp.content)


# ── 법령 풀네임 → 약칭 매핑 (참조 추출용) ──
_FULL_TO_SHORT = {}
for _law in LAW_LIST:
    _FULL_TO_SHORT[_law["name"]] = _law["short"]
    _FULL_TO_SHORT[_law["short"]] = _law["short"]


def _extract_refs(text: str) -> list:
    """조문 텍스트에서 위임 참조(「법령명」 제X조)를 추출한다.
    
    Returns:
        [{"law": "국가계약법 시행규칙", "article": "제24조", "raw": "원문"}]
    """
    refs = []
    seen = set()
    pattern = r'「([^」]+)」[^제]{0,15}(제\d+조(?:의\d+)?)'
    for match in re.finditer(pattern, text):
        law_full = match.group(1).strip()
        art_no = match.group(2)
        # 약칭 변환
        short = None
        for full_key in sorted(_FULL_TO_SHORT.keys(), key=len, reverse=True):
            if full_key in law_full or law_full in full_key:
                short = _FULL_TO_SHORT[full_key]
                break
        if not short:
            short = law_full  # 매핑 없으면 원래 이름 사용
        key = f"{short} {art_no}"
        if key not in seen:
            seen.add(key)
            refs.append({"law": short, "article": art_no, "raw": match.group(0)})
    return refs


def _clean_html(text: str) -> str:
    """HTML 태그 제거."""
    text = re.sub(r'<br\s*/?>', '\n', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = text.replace('&nbsp;', ' ').replace('&#160;', ' ')
    return text.strip()


def fetch_law_full(mst: str) -> list[dict]:
    """법령 전체 조문 수집 (법제처 API 직접 호출)."""
    articles = []
    
    try:
        # 법령 전문 조회 (target=law)
        root = _get_xml({"target": "law", "MST": mst})
        
        # 조문 목록 추출
        jo_elements = root.findall('.//조문단위')
        if not jo_elements:
            # 다른 XML 구조 시도
            jo_elements = root.findall('.//조문')
        
        if jo_elements:
            for jo_el in jo_elements:
                jo_no_el = jo_el.find('조문번호')
                jo_title_el = jo_el.find('조문제목')
                jo_content_el = jo_el.find('조문내용')
                
                jo_no = jo_no_el.text.strip() if jo_no_el is not None and jo_no_el.text else ""
                jo_title = jo_title_el.text.strip() if jo_title_el is not None and jo_title_el.text else ""
                jo_content = _clean_html(jo_content_el.text) if jo_content_el is not None and jo_content_el.text else ""
                
                # 항 내용 수집
                hang_parts = []
                for hang_el in jo_el.findall('.//항'):
                    hang_no_el = hang_el.find('항번호')
                    hang_content_el = hang_el.find('항내용')
                    if hang_content_el is not None and hang_content_el.text:
                        hang_text = _clean_html(hang_content_el.text)
                        hang_parts.append(hang_text)
                    
                    # 호 내용
                    for ho_el in hang_el.findall('.//호'):
                        ho_content_el = ho_el.find('호내용')
                        if ho_content_el is not None and ho_content_el.text:
                            ho_text = _clean_html(ho_content_el.text)
                            hang_parts.append("  " + ho_text)
                        
                        # 목 내용
                        for mok_el in ho_el.findall('.//목'):
                            mok_content_el = mok_el.find('목내용')
                            if mok_content_el is not None and mok_content_el.text:
                                mok_text = _clean_html(mok_content_el.text)
                                hang_parts.append("    " + mok_text)
                
                full_text = jo_content
                if hang_parts:
                    full_text = full_text + "\n" + "\n".join(hang_parts) if full_text else "\n".join(hang_parts)
                
                if not full_text or len(full_text.strip()) < 5:
                    continue
                
                # 조번호 정규화 (예: "25" → "제25조")
                # 조문내용에서 실제 조문번호 추출 (제6조의2 등 구분)
                article_key = f"제{jo_no}조" if jo_no and not jo_no.startswith("제") else jo_no
                
                # 법제처 API는 제6조/제6조의2/제6조의3 등을 모두 jo_no="6"으로 반환
                # → 조문내용 텍스트에서 실제 조문번호를 추출하여 key 중복 방지
                real_no_match = re.match(r'(제\d+조(?:의\d+)?)', full_text.strip())
                if real_no_match:
                    real_key = real_no_match.group(1)
                    if real_key != article_key:
                        article_key = real_key
                
                articles.append({
                    "article": article_key,
                    "title": jo_title,
                    "text": full_text.strip(),
                })
        
        if not articles:
            # XML 구조가 다른 경우: 전체 텍스트 추출
            all_text = ET.tostring(root, encoding='unicode', method='text')
            if all_text and len(all_text.strip()) > 50:
                # 조문번호로 분할 시도
                parts = re.split(r'(제\d+조(?:의\d+)?)', all_text)
                for i in range(1, len(parts), 2):
                    art_no = parts[i]
                    art_text = parts[i+1].strip() if i+1 < len(parts) else ""
                    # 제목 추출
                    title_match = re.search(r'[\(（]([^)）]+)[）\)]', art_text[:100])
                    title = title_match.group(1) if title_match else ""
                    full = f"{art_no}({title}) {art_text}" if title else f"{art_no} {art_text}"
                    articles.append({
                        "article": art_no,
                        "title": title,
                        "text": full[:3000].strip(),
                    })
    
    except Exception as e:
        print(f"    [ERROR] {e}")
    
    return articles


def main():
    print("=" * 60)
    print("법제처 API 직접 호출 — 핵심 법령 전체 조문 수집")
    print(f"인증키: {OC}")
    print("=" * 60)
    
    # 기존 DB 로드 (정상 데이터 보존)
    existing_db = {}
    if os.path.exists(OUTPUT_PATH):
        try:
            with open(OUTPUT_PATH, "r", encoding="utf-8") as f:
                existing_db = json.load(f)
        except:
            pass
    
    db = {}
    total_articles = 0
    total_chars = 0
    
    for i, law in enumerate(LAW_LIST):
        mst = law["mst"]
        short = law["short"]
        name = law["name"]
        
        print(f"\n[{i+1}/{len(LAW_LIST)}] {short} (MST: {mst})")
        
        articles = fetch_law_full(mst)
        
        if articles:
            db[short] = {
                "mst": mst,
                "full_name": name,
                "short_name": short,
                "article_count": len(articles),
                "collected_at": time.strftime("%Y-%m-%d %H:%M"),
                "source": "법제처 API 직접",
                "articles": {}
            }
            for art in articles:
                # 위임 참조 자동 추출
                cross_refs = _extract_refs(art["text"])
                db[short]["articles"][art["article"]] = {
                    "title": art["title"],
                    "text": art["text"],
                    "lookup_key": f"{short} {art['article']}",
                    "cross_refs": [{"law": r["law"], "article": r["article"]} for r in cross_refs],
                }
                total_articles += 1
                total_chars += len(art["text"])
            
            # 참조 통계
            ref_count = sum(len(db[short]["articles"][a]["cross_refs"]) for a in db[short]["articles"])
            print(f"    ✅ {len(articles)}개 조문, {sum(len(a['text']) for a in articles):,}자, 참조 {ref_count}건")
        else:
            # 기존 DB에서 정상 데이터 보존
            if short in existing_db:
                existing_articles = existing_db[short].get("articles", {})
                clean_articles = {k: v for k, v in existing_articles.items() 
                                  if "MCP 호출 오류" not in v.get("text", "")}
                if clean_articles:
                    existing_db[short]["articles"] = clean_articles
                    existing_db[short]["article_count"] = len(clean_articles)
                    db[short] = existing_db[short]
                    total_articles += len(clean_articles)
                    total_chars += sum(len(v["text"]) for v in clean_articles.values())
                    print(f"    ⚠️ API 실패 — 기존 DB에서 {len(clean_articles)}개 조문 보존")
                    continue
            print(f"    ❌ 수집 실패")
        
        time.sleep(0.5)  # 예의상 0.5초 간격
    
    # key_articles.json 병합 (누락분 보강)
    ka_path = os.path.join(_ROOT, "data", "key_articles.json")
    if os.path.exists(ka_path):
        with open(ka_path, "r", encoding="utf-8") as f:
            ka = json.load(f)
        
        ka_mapping = {
            "R_DIRECT_GENERAL_SMALL_AMOUNT": ("지방계약법 시행령", "제25조", "수의계약에 의할 수 있는 경우"),
            "R_LOCAL_REGIONAL_JOINT_CONTRACT": ("지방계약법 시행령", "제88조", "공동계약"),
            "R_NATIONAL_REGIONAL_JOINT_CONTRACT": ("국가계약법 시행령", "제72조", "공동계약"),
            "R_REGIONAL_RESTRICTION_GOODS": ("지방계약법 시행령", "제20조", "제한입찰에 의할 계약과 제한사항 등"),
        }
        
        for ka_key, (law_short, art_no, title) in ka_mapping.items():
            ka_text = ka.get(ka_key, "")
            if not ka_text or len(ka_text) < 50:
                continue
            if law_short not in db:
                db[law_short] = {"mst": "", "full_name": law_short, "short_name": law_short, 
                                 "article_count": 0, "collected_at": "key_articles 병합", "articles": {}}
            existing_text = db[law_short]["articles"].get(art_no, {}).get("text", "")
            if len(ka_text) > len(existing_text):
                db[law_short]["articles"][art_no] = {"title": title, "text": ka_text, 
                                                     "lookup_key": f"{law_short} {art_no}", "source": "key_articles"}
                print(f"  [KA_MERGE] {law_short} {art_no}: {len(ka_text)} chars")
            db[law_short]["article_count"] = len(db[law_short]["articles"])
    
    # 저장
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    
    file_size = os.path.getsize(OUTPUT_PATH)
    print(f"\n{'=' * 60}")
    print(f"완료: {len(db)}개 법령, {total_articles}개 조문, {total_chars:,}자")
    print(f"파일: {OUTPUT_PATH} ({file_size:,} bytes)")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
