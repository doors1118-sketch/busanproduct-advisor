import sqlite3

db_path = r'cache\company\cache_new\company_master_cache.sqlite'
try:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    print('--- 여성기업 ---')
    cur.execute("SELECT company_name, product_keywords FROM companies WHERE policy_subtypes_json LIKE '%여성%' AND product_keywords_json IS NOT NULL LIMIT 1;")
    print(cur.fetchall())

    print('--- 쇼핑몰 ---')
    cur.execute("SELECT company_name, product_keywords_json FROM companies WHERE is_shopping_mall=1 AND product_keywords_json IS NOT NULL LIMIT 1;")
    print(cur.fetchall())

    print('--- 혁신제품 ---')
    cur.execute("SELECT company_name, product_keywords_json FROM companies WHERE certified_product_types_json LIKE '%혁신%' AND product_keywords_json IS NOT NULL LIMIT 1;")
    print(cur.fetchall())

    print('--- 우수조달 ---')
    cur.execute("SELECT company_name, product_keywords_json FROM companies WHERE certified_product_types_json LIKE '%우수%' AND product_keywords_json IS NOT NULL LIMIT 1;")
    print(cur.fetchall())
except Exception as e:
    print('DB Error:', e)
