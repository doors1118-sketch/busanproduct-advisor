import sqlite3
db_path = r'c:\Users\COMTREE\Desktop\메뉴얼 제작\app\data\legal_db_v0_1_3.sqlite'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("PRAGMA table_info(legal_source)")
print([r[1] for r in cur.fetchall()])
conn.close()
