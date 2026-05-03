import requests

base = "http://127.0.0.1:8000"

def fetch_and_print(endpoint, name):
    try:
        r = requests.get(f"{base}{endpoint}?limit=5")
        if r.status_code == 200:
            data = r.json().get('data', [])
            print(f"--- {name} ---")
            for item in data[:3]:
                if "company_name" in item:
                    print(item.get("company_name"), item.get("main_products", item.get("product_name", item.get("product_keywords"))))
                elif "product_name" in item:
                    print(item.get("company_name", item.get("supplier_name", "N/A")), item.get("product_name"))
                else:
                    print(item)
    except Exception as e:
        print(e)

fetch_and_print("/api/chatbot/shopping-mall/list", "Shopping Mall")
fetch_and_print("/api/chatbot/product/certified-list", "Certified Product")
fetch_and_print("/api/chatbot/company/policy-list", "Policy Company")
