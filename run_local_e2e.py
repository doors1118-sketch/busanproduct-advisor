import requests, json

url = "http://127.0.0.1:8001/chat"
headers = {"Content-Type": "application/json"}

queries = {
    "A": "7천만원으로 컴퓨터 구매해야 한다. 가급적 지역업체랑 계약하고 싶은데 방법이 있을까?",
    "B": "8천만원 물품 수의계약 가능해?",
    "C": "2천만원 컴퓨터 부산업체랑 계약하고 싶어",
    "D": "CCTV 부산업체 추천해줘"
}

for label, q in queries.items():
    print(f"Requesting {label}...")
    res = requests.post(url, headers=headers, json={"message": q, "history": [], "agency_type": "지방자치단체"})
    if res.status_code == 200:
        with open(f"scenario_{label.lower()}_raw.json", "w", encoding="utf-8-sig") as f:
            json.dump(res.json(), f, ensure_ascii=False, indent=2)
    else:
        print(f"Error {label}: {res.status_code} {res.text}")

print("Done")
