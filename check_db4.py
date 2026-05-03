import sqlite3

db_path = r'cache\company\cache_new\company_master_cache.sqlite'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("== Policy ==")
cur.execute("SELECT company_name, main_products_json FROM companies WHERE json_extract(policy_subtypes_json, '$') LIKE '%여성%' LIMIT 2")
for r in cur.fetchall(): print(r)

print("== MAS ==")
cur.execute("SELECT company_name, main_products_json FROM companies WHERE is_shopping_mall = 1 LIMIT 2")
for r in cur.fetchall(): print(r)

print("== Cert ==")
cur.execute("SELECT company_name, main_products_json FROM companies WHERE json_extract(certified_product_types_json, '$') LIKE '%혁신%' OR json_extract(certified_product_types_json, '$') LIKE '%우수%' LIMIT 2")
for r in cur.fetchall(): print(r)
