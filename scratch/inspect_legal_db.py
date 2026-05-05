"""법령 DB 스키마 및 데이터 확인 스크립트"""
import sqlite3
import json

DB_PATH = r"c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_db_v0_1_3.sqlite"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 1. 테이블 목록
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cursor.fetchall()]
print("=== Tables ===")
for t in tables:
    print(f"  {t}")

# 2. 각 테이블 스키마 + 행 수
for t in tables:
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE name='{t}'")
    schema = cursor.fetchone()
    cursor.execute(f"SELECT COUNT(*) FROM [{t}]")
    cnt = cursor.fetchone()[0]
    print(f"\n=== {t} ({cnt} rows) ===")
    if schema and schema[0]:
        print(schema[0])

# 3. legal_sources 테이블이 있으면 title 샘플 출력
if "legal_sources" in tables:
    print("\n=== legal_sources 샘플 (처음 30개 title) ===")
    cursor.execute("SELECT id, title, source_type, law_category FROM legal_sources LIMIT 30")
    for row in cursor.fetchall():
        print(f"  [{row[2]}|{row[3]}] {row[1][:60]}  (id={row[0][:8]}...)")
    
    # 지방계약법 관련 검색
    print("\n=== '지방자치단체' 포함 title ===")
    cursor.execute("SELECT id, title FROM legal_sources WHERE title LIKE '%지방자치단체%'")
    for row in cursor.fetchall():
        print(f"  {row[1]}  (id={row[0]})")
    
    print("\n=== '국가를 당사자' 포함 title ===")
    cursor.execute("SELECT id, title FROM legal_sources WHERE title LIKE '%국가를 당사자%'")
    for row in cursor.fetchall():
        print(f"  {row[1]}  (id={row[0]})")

    print("\n=== '조달사업' 포함 title ===")
    cursor.execute("SELECT id, title FROM legal_sources WHERE title LIKE '%조달사업%'")
    for row in cursor.fetchall():
        print(f"  {row[1]}  (id={row[0]})")

    print("\n=== '중소기업' 포함 title ===")
    cursor.execute("SELECT id, title FROM legal_sources WHERE title LIKE '%중소기업%'")
    for row in cursor.fetchall():
        print(f"  {row[1]}  (id={row[0]})")

    # source_chain_status 통계 (source_map에서)
    print("\n=== source_type 분포 ===")
    cursor.execute("SELECT source_type, COUNT(*) FROM legal_sources GROUP BY source_type ORDER BY COUNT(*) DESC")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}건")

    print("\n=== law_category 분포 ===")
    cursor.execute("SELECT law_category, COUNT(*) FROM legal_sources GROUP BY law_category ORDER BY COUNT(*) DESC")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}건")

conn.close()
