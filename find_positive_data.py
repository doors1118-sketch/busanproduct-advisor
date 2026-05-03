import requests
import json

base_url = "http://127.0.0.1:8000/api/chatbot"

def get_list(endpoint):
    try:
        r = requests.get(f"{base_url}/{endpoint}")
        if r.status_code == 200:
            return r.json().get('data', [])
        print(f"Error {r.status_code} on {endpoint}")
    except Exception as e:
        print(f"Exception on {endpoint}: {e}")
    return []

print("=== Positive Data Finder ===")
products = get_list("company/product-list?limit=10")
print(f"Products: {products[:3]}")

mall = get_list("company/shopping-mall/list?limit=10")
print(f"Shopping Mall: {mall[:3]}")

cert = get_list("company/certified-list?limit=10")
print(f"Certified: {cert[:3]}")

license = get_list("company/license-list?limit=10")
print(f"License: {license[:3]}")
