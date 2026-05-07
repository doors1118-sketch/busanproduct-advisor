"""
37종 핵심 법령 전체 조문 수집 → law_articles_db.json 구축
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

외부 MCP(korean-law-mcp → 법제처 API)에서 1회 다운로드하여
내부 DB로 영구 저장. 이후 MCP preflight는 이 파일만 참조.

실행: python collect_all_law_articles.py
서버: cd /opt/advisor/app && python3 collect_all_law_articles.py
"""
import os
import re
import json
import time
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(os.path.dirname(_root), ".env"))

import mcp_client as mcp

# ─────────────────────────────────────────────
# 수집 대상: 13개 핵심 법령 (ingest_laws.py LAW_LIST)
# ─────────────────────────────────────────────
LAW_LIST = [
    # L1: 핵심 계약법
    {"mst": "253973", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률", "short": "지방계약법"},
    {"mst": "281055", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행령", "short": "지방계약법 시행령"},
    {"mst": "282729", "name": "지방자치단체를 당사자로 하는 계약에 관한 법률 시행규칙", "short": "지방계약법 시행규칙"},
    {"mst": "277151", "name": "국가를 당사자로 하는 계약에 관한 법률", "short": "국가계약법"},
    {"mst": "280803", "name": "국가를 당사자로 하는 계약에 관한 법률 시행령", "short": "국가계약법 시행령"},
    {"mst": "282607", "name": "국가를 당사자로 하는 계약에 관한 법률 시행규칙", "short": "국가계약법 시행규칙"},
    # L1: 중소기업 구매촉진
    {"mst": "277129", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률", "short": "중소기업구매촉진법"},
    {"mst": "281341", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행령", "short": "중소기업구매촉진법 시행령"},
    {"mst": "253373", "name": "중소기업제품 구매촉진 및 판로지원에 관한 법률 시행규칙", "short": "중소기업구매촉진법 시행규칙"},
    # L2: 조달사업법
    {"mst": "277155", "name": "조달사업에 관한 법률", "short": "조달사업법"},
    {"mst": "280891", "name": "조달사업에 관한 법률 시행령", "short": "조달사업법 시행령"},
    {"mst": "282675", "name": "조달사업에 관한 법률 시행규칙", "short": "조달사업법 시행규칙"},
    # L2: 공기업 계약사무규칙
    {"mst": "285569", "name": "공기업ㆍ준정부기관 계약사무규칙", "short": "공기업계약사무규칙"},
]

OUTPUT_PATH = os.path.join(_root, "data", "law_articles_db.json")

def fetch_articles(mst: str) -> list[dict]:
    """MCP get_law_text로 조문 수집."""
    try:
        toc_text = mcp.get_law_text(mst=mst)
    except Exception as e:
        print(f"    [ERROR] get_law_text({mst}): {e}")
        return []
    
    if not toc_text or len(toc_text) < 10:
        print(f"    [WARN] 빈 응답")
        return []
    
    # 조번호 추출
    article_numbers = re.findall(r'(제\d+조(?:의\d+)?)', toc_text)
    seen = set()
    unique_articles = []
    for a in article_numbers:
        if a not in seen:
            seen.add(a)
            unique_articles.append(a)
    
    if not unique_articles:
        # 목차에서 조번호를 못 찾으면 전체 텍스트를 1건으로 저장
        return [{"article": "전문", "title": "", "text": toc_text.strip()}]
    
    print(f"    → {len(unique_articles)}개 조문 발견")
    
    articles = []
    for jo_no in unique_articles:
        try:
            jo_text = mcp.get_law_text(mst=mst, jo=jo_no)
            if jo_text and len(jo_text) > 10:
                title_match = re.search(r'[（\(]([^)）]+)[）\)]', jo_text[:200])
                jo_title = title_match.group(1) if title_match else ""
                articles.append({
                    "article": jo_no,
                    "title": jo_title,
                    "text": jo_text.strip(),
                })
        except Exception as e:
            print(f"    [SKIP] {jo_no}: {e}")
        time.sleep(0.2)
    
    return articles


def main():
    print("=" * 60)
    print("핵심 법령 전체 조문 수집 → law_articles_db.json")
    print("=" * 60)
    
    db = {}
    total_articles = 0
    total_chars = 0
    
    for i, law in enumerate(LAW_LIST):
        mst = law["mst"]
        short = law["short"]
        name = law["name"]
        
        print(f"\n[{i+1}/{len(LAW_LIST)}] {short} (MST: {mst})")
        
        articles = fetch_articles(mst)
        
        if articles:
            db[short] = {
                "mst": mst,
                "full_name": name,
                "short_name": short,
                "article_count": len(articles),
                "collected_at": time.strftime("%Y-%m-%d %H:%M"),
                "articles": {}
            }
            for art in articles:
                key = f"{short} {art['article']}"
                db[short]["articles"][art["article"]] = {
                    "title": art["title"],
                    "text": art["text"],
                    "lookup_key": key,
                }
                total_articles += 1
                total_chars += len(art["text"])
            
            print(f"    ✅ {len(articles)}개 조문, {sum(len(a['text']) for a in articles):,}자")
        else:
            print(f"    ❌ 수집 실패")
    
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
