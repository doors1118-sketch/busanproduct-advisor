"""법령 DB 핵심 법령 매핑 확인"""
import sqlite3

DB_PATH = r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_db_v0_1_3.sqlite"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 핵심 법령 검색
searches = [
    ("지방자치단체", "%지방자치단체%"),
    ("국가를 당사자", "%국가를 당사자%"),
    ("조달사업", "%조달사업%"),
    ("중소기업", "%중소기업%"),
    ("지방재정법", "%지방재정법%"),
    ("건설산업", "%건설산업%"),
    ("소프트웨어", "%소프트웨어%"),
    ("엔지니어링", "%엔지니어링%"),
    ("계약예규", "%계약예규%"),
    ("입찰", "%입찰%"),
    ("낙찰", "%낙찰%"),
    ("적격심사", "%적격심사%"),
    ("지역", "%지역%"),
    ("수의계약", "%수의계약%"),
    ("공동도급", "%공동도급%"),
    ("제한경쟁", "%제한경쟁%"),
]

for label, pattern in searches:
    cursor.execute("SELECT source_id, source_name, source_type, law_category, review_status FROM legal_source WHERE source_name LIKE ?", (pattern,))
    rows = cursor.fetchall()
    if rows:
        print(f"\n=== '{label}' 검색 ({len(rows)}건) ===")
        for row in rows:
            print(f"  [{row[3]}|{row[2]}|{row[4]}] {row[1][:80]}")
            print(f"    id={row[0]}")

# source_chain_status 요약 (source_map json에서)
print("\n=== review_status 분포 ===")
cursor.execute("SELECT review_status, COUNT(*) FROM legal_source GROUP BY review_status ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}건")

print("\n=== source_type 분포 ===")
cursor.execute("SELECT source_type, COUNT(*) FROM legal_source GROUP BY source_type ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}건")

print("\n=== law_category 분포 ===")
cursor.execute("SELECT law_category, COUNT(*) FROM legal_source GROUP BY law_category ORDER BY COUNT(*) DESC")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}건")

# 전체 목록 (source_type=law or law_decree 만)
print("\n=== 법률/시행령 전체 목록 ===")
cursor.execute("SELECT source_id, source_name, law_category FROM legal_source WHERE source_type IN ('law', 'law_decree') ORDER BY source_name")
for row in cursor.fetchall():
    print(f"  [{row[2]}] {row[1]}")
    print(f"    id={row[0]}")

conn.close()
