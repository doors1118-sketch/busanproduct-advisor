import sqlite3
import json

db_path = r'cache\company\cache_new\company_master_cache.sqlite'
try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(companies);")
    columns = [r[1] for r in cur.fetchall()]
    print(f"Columns: {columns}")
    
    cur.execute(f"SELECT * FROM companies LIMIT 20;")
    for row in cur.fetchall():
        print(row)
except Exception as e:
    print('DB Error:', e)
