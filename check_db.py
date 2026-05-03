import sqlite3
import json

db_path = r'cache\company\cache_new\company_master_cache.sqlite'
try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Tables: {tables}")
    
    if "company_master" in tables:
        cur.execute("SELECT company_name, product_keywords, policy_tags, is_shopping_mall FROM company_master WHERE product_keywords IS NOT NULL LIMIT 20;")
        for row in cur.fetchall():
            print(row)
except Exception as e:
    print('DB Error:', e)
