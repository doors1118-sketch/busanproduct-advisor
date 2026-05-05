"""법령 DB 핵심 법령 매핑 확인 - UTF-8 파일 출력"""
import sqlite3

DB_PATH = r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_db_v0_1_3.sqlite"
OUT_PATH = r"c:\Users\COMTREE\Desktop\메뉴얼 제작\scratch\legal_db_dump.txt"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

lines = []

# 법률/시행령 전체 목록
lines.append("=== 법률/시행령 (source_type=law|law_decree|law_rule) ===")
cursor.execute("SELECT source_id, source_name, law_category, source_type, review_status FROM legal_source WHERE source_type IN ('law', 'law_decree', 'law_rule') ORDER BY source_name")
for row in cursor.fetchall():
    lines.append(f"  [{row[2]}|{row[3]}|{row[4]}] {row[1]}")
    lines.append(f"    id={row[0]}")

# 핵심 키워드별 검색
searches = [
    ("지방자치단체", "%지방자치단체%"),
    ("국가를 당사자", "%국가를 당사자%"),
    ("조달사업", "%조달사업%"),
    ("중소기업", "%중소기업%"),
    ("건설산업", "%건설산업%"),
    ("공동도급", "%공동도급%"),
    ("수의계약", "%수의계약%"),
    ("제한경쟁", "%제한경쟁%"),
    ("지역", "%지역%"),
    ("적격심사", "%적격심사%"),
    ("입찰", "%입찰%"),
    ("낙찰", "%낙찰%"),
    ("계약예규", "%계약예규%"),
    ("계약집행", "%계약집행%"),
]

for label, pattern in searches:
    cursor.execute("SELECT source_id, source_name, source_type, law_category, review_status FROM legal_source WHERE source_name LIKE ?", (pattern,))
    rows = cursor.fetchall()
    if rows:
        lines.append(f"\n=== '{label}' 검색 ({len(rows)}건) ===")
        for row in rows:
            lines.append(f"  [{row[3]}|{row[2]}|{row[4]}] {row[1]}")
            lines.append(f"    id={row[0]}")

# source_map에서 unmatched_query_terms 수집
import json
SMAP_PATH = r"c:\Users\COMTREE\Desktop\메뉴얼 제작\purchase_support_rule_source_map.json"
with open(SMAP_PATH, "r", encoding="utf-8") as f:
    smap = json.load(f)

lines.append("\n\n=== Source Map 현황 ===")
for rule_id, entry in smap.items():
    status = entry.get("source_chain_status", "unknown")
    unmatched = entry.get("unmatched_query_terms", [])
    primary_count = len(entry.get("primary_source_ids", []))
    lines.append(f"  [{status}] {rule_id} (primary={primary_count}, unmatched={unmatched})")

# source_chain_status 통계
from collections import Counter
status_counts = Counter(e["source_chain_status"] for e in smap.values())
lines.append(f"\n=== source_chain_status 분포 ===")
for status, cnt in status_counts.most_common():
    lines.append(f"  {status}: {cnt}건")

conn.close()

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"결과를 {OUT_PATH}에 저장했습니다.")
print(f"총 {len(lines)}줄")
