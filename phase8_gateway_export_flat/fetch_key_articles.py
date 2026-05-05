"""
fetch_key_articles.py
법제처 API를 통해 핵심 조문 본문을 조회하고 key_articles.json으로 저장합니다.
"""
import requests
import xml.etree.ElementTree as ET
import json
import os

BASE_URL = "http://www.law.go.kr/DRF"
OC = "busanproduct1"
OUTPUT_PATH = "app/data/key_articles.json"

TARGETS = [
    {"mst": "281055", "law_name": "지방계약법 시행령", "articles": ["20", "25", "30", "88"]},
    {"mst": "280803", "law_name": "국가계약법 시행령", "articles": ["21", "26", "72", "72의2"]},
]

RULE_TO_ARTICLES = {
    "R_DIRECT_GENERAL_SMALL_AMOUNT": ["지방계약법 시행령 제25조", "지방계약법 시행령 제30조"],
    "R_DIRECT_GENERAL_SMALL_AMOUNT_NOT_PRIMARY": ["지방계약법 시행령 제25조", "지방계약법 시행령 제30조"],
    "R_LOCAL_REGIONAL_JOINT_CONTRACT": ["지방계약법 시행령 제88조"],
    "R_NATIONAL_REGIONAL_JOINT_CONTRACT": ["국가계약법 시행령 제72조"],
    "R_REGIONAL_RESTRICTION_GOODS": ["지방계약법 시행령 제20조"],
    "R_REGIONAL_RESTRICTION_SERVICE": ["지방계약법 시행령 제20조"],
    "R_REGIONAL_RESTRICTION_CONSTRUCTION": ["지방계약법 시행령 제20조"],
}

def api_get(endpoint, params, timeout=15):
    params["OC"] = OC
    params["type"] = "XML"
    r = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=timeout)
    r.raise_for_status()
    return ET.fromstring(r.content)

def fetch_articles():
    article_db = {}
    for target in TARGETS:
        mst = target["mst"]
        law_name = target["law_name"]
        print(f"Fetching {law_name} (MST: {mst})...")
        
        try:
            root = api_get("lawService.do", {"target": "law", "MST": mst})
        except Exception as e:
            print(f"Failed to fetch {law_name}: {e}")
            continue
            
        for jo in root.findall(".//조문단위"):
            jo_no_el = jo.find("조문번호")
            if jo_no_el is not None:
                branch_no_el = jo.find("조문가지번호")
                article_key_num = jo_no_el.text
                if branch_no_el is not None and branch_no_el.text and branch_no_el.text != "0":
                    article_key_num = f"{jo_no_el.text}의{branch_no_el.text}"
                    
                if article_key_num not in target["articles"]:
                    continue
                    
                title_el = jo.find("조문제목")
                title = title_el.text if title_el is not None else ""
                
                # 조문 내용 구성
                lines = []
                content = jo.find("조문내용")
                if content is not None and content.text:
                    lines.append(content.text.strip())
                
                for hang in jo.findall(".//항"):
                    hang_el = hang.find("항내용")
                    if hang_el is not None and hang_el.text:
                        lines.append("  " + hang_el.text.strip())
                        
                    for ho in hang.findall(".//호"):
                        ho_el = ho.find("호내용")
                        if ho_el is not None and ho_el.text:
                            lines.append("    " + ho_el.text.strip())
                            
                        for mok in ho.findall(".//목"):
                            mok_el = mok.find("목내용")
                            if mok_el is not None and mok_el.text:
                                lines.append("      " + mok_el.text.strip())
                
                full_text = "\n".join(lines)
                key = f"{law_name} 제{article_key_num}조"
                article_db[key] = {
                    "law_name": law_name,
                    "article_no": article_key_num,
                    "title": title,
                    "full_text": full_text
                }
                print(f"  Saved: {key}")

    # Build final result mapping rule_id -> list of article texts
    rule_evidence_db = {}
    for rule_id, article_keys in RULE_TO_ARTICLES.items():
        texts = []
        for ak in article_keys:
            if ak in article_db:
                texts.append(f"[{ak} {article_db[ak]['title']}]\n{article_db[ak]['full_text']}")
        if texts:
            rule_evidence_db[rule_id] = "\n\n".join(texts)

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(rule_evidence_db, f, indent=2, ensure_ascii=False)
    print(f"Saved evidence mapping for {len(rule_evidence_db)} rules to {OUTPUT_PATH}")

if __name__ == "__main__":
    fetch_articles()
