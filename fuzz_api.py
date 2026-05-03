from app.company_api import search_shopping_mall_product, search_innovation_product, search_by_policy, search_certified_product

keywords = ["컴퓨터", "노트북", "서버", "CCTV", "LED", "안전펜스", "가구", "의자", "책상", "방송장비", "에어컨"]

print("--- Shopping Mall ---")
for kw in keywords:
    res = search_shopping_mall_product(kw)
    cands = res.get("data", res.get("candidates", [])) if isinstance(res, dict) else []
    if cands:
        print(f"Found {len(cands)} for {kw}")
        
print("--- Innovation ---")
for kw in keywords:
    res = search_innovation_product(kw)
    cands = res.get("data", res.get("candidates", [])) if isinstance(res, dict) else []
    if cands:
        print(f"Found {len(cands)} for {kw}")

print("--- Certified ---")
for kw in keywords:
    res = search_certified_product(kw, "NET")
    cands = res.get("data", res.get("candidates", [])) if isinstance(res, dict) else []
    if cands:
        print(f"Found {len(cands)} for {kw}")

print("--- Policy ---")
for kw in ["여성기업", "장애인기업", "사회적기업"]:
    res = search_by_policy(kw)
    cands = res.get("data", res.get("candidates", [])) if isinstance(res, dict) else []
    if cands:
        print(f"Found {len(cands)} for {kw}")
